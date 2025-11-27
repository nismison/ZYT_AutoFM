#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import traceback
import shutil

from peewee import DoesNotExist

from config import (
    db,
    IMMICH_EXTERNAL_HOST_ROOT,
    FILE_STATUS_COMPLETED,
    FILE_STATUS_UPLOADING,
    SESSION_STATUS_READY_TO_COMPLETE,
    SESSION_STATUS_COMPLETED,
)
from db import File, UploadSession, UploadPart
from utils.logger import log_line


# =========================
# 路径相关工具函数
# =========================

def ensure_immich_root():
    """
    确保 IMMICH_EXTERNAL_HOST_ROOT 目录存在。
    只做一次目录创建，避免合并时因为目录不存在而失败。
    """
    os.makedirs(IMMICH_EXTERNAL_HOST_ROOT, exist_ok=True)


def get_chunk_path(fingerlog_line: str, part_number: int) -> str:
    """
    构造分片文件路径。

    约定：所有分片直接放在 IMMICH_EXTERNAL_HOST_ROOT 根目录下，
    不使用子文件夹，命名规则例如：
        /immich-external-library/<fingerlog_line>_1.part
        /immich-external-library/<fingerlog_line>_2.part

    上传接口保存分片时必须使用相同规则。
    """
    filename = f"{fingerlog_line}_{part_number}.part"
    return os.path.join(IMMICH_EXTERNAL_HOST_ROOT, filename)


def get_final_file_path(file: File) -> str:
    """
    构造最终合并后的文件路径。

    约定：File.cos_key 存储的是「最终文件名」（不带目录），
    合并后的文件直接放到 IMMICH_EXTERNAL_HOST_ROOT 根目录下：
        /immich-external-library/<file.cos_key>
    """
    filename = file.cos_key  # 例如: "<fingerlog_line>_original.mp4"
    return os.path.join(IMMICH_EXTERNAL_HOST_ROOT, filename)


# =========================
# 合并逻辑
# =========================

def merge_one_session(session: UploadSession):
    """
    合并单个 UploadSession 对应的文件分片。

    流程：
      1. 读取所有 DONE 分片；
      2. 校验分片数量是否完整；
      3. 按 part_number 顺序顺序写入到临时文件；
      4. 原子 rename 为最终文件；
      5. 删除所有分片文件；
      6. 更新 File / UploadSession 状态。
    """
    file = session.file

    # 1. 读取分片记录
    parts_query = (
        UploadPart
        .select()
        .where(
            (UploadPart.file == file) &
            (UploadPart.status == "DONE")
        )
        .order_by(UploadPart.part_number)
    )

    parts = list(parts_query)
    if not parts:
        # 没有任何分片，数据异常，回退状态避免死循环
        log_line(f"[merge_worker] No parts found for file fingerlog_line={file.fingerlog_line}, "
                 f"session_id={session.id}, skip.")
        session.status = FILE_STATUS_UPLOADING
        session.save()
        return

    if len(parts) != session.total_chunks:
        # 分片数量不完整，回退状态，交给业务层重新处理
        log_line(f"[merge_worker] Incomplete parts for file fingerlog_line={file.fingerlog_line}, "
                 f"session_id={session.id}, "
                 f"got={len(parts)}, expected={session.total_chunks}, skip.")
        session.status = FILE_STATUS_UPLOADING
        session.save()
        return

    # 2. 构造最终文件路径和临时文件路径
    ensure_immich_root()
    final_path = get_final_file_path(file)
    tmp_path = final_path + ".tmp"

    log_line(f"[merge_worker] Start merging file fingerlog_line={file.fingerlog_line}, "
             f"session_id={session.id}, final_path={final_path}")

    # 3. 顺序合并分片
    try:
        # 使用原子替换：先写 tmp，再 rename 到 final_path
        with open(tmp_path, "wb") as out_f:
            for part in parts:
                chunk_path = get_chunk_path(file.fingerlog_line, part.part_number)

                if not os.path.exists(chunk_path):
                    # 分片文件丢失，认为当前任务失败，回退状态
                    log_line(f"[merge_worker] Chunk file missing: {chunk_path}, abort merge.")
                    raise FileNotFoundError(chunk_path)

                with open(chunk_path, "rb") as in_f:
                    # 使用大一点的 buffer，效率高一些
                    shutil.copyfileobj(in_f, out_f, length=1024 * 1024)  # type: ignore[arg-type]

        # 原子替换：避免中途被读到半拉文件
        os.replace(tmp_path, final_path)

        # 4. 删除所有分片文件
        for part in parts:
            chunk_path = get_chunk_path(file.fingerlog_line, part.part_number)
            try:
                os.remove(chunk_path)
            except FileNotFoundError:
                # 已经不存在就算了，不影响整体成功
                pass

        # 5. 更新数据库状态
        file.status = FILE_STATUS_COMPLETED
        # url 字段你可以按自己前后端的访问方式改成完整 URL，
        # 这里先用 cos_key（即文件名）占位，代表「Immich 外部库根目录下的这个文件」
        file.url = file.cos_key
        file.save()

        session.status = SESSION_STATUS_COMPLETED
        session.save()

        log_line(f"[merge_worker] Merge success for fingerlog_line={file.fingerlog_line}, "
                 f"final_path={final_path}")

    except Exception as e:
        # 任何异常都打印出来，回退状态避免死循环
        traceback.print_exc()
        log_line(f"[merge_worker] Merge failed for fingerlog_line={file.fingerlog_line}: {e}")

        # 尝试清理 tmp 文件，避免磁盘垃圾
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

        # 回退到 UPLOADING 状态，等待业务决定如何处理（例如重新标记为 READY_TO_COMPLETE）
        session.status = FILE_STATUS_UPLOADING
        session.save()


def poll_and_merge_once() -> bool:
    """
    轮询一遍数据库，处理一条待合并任务。

    返回:
      - True: 找到并处理了一条任务（无论成功还是失败）
      - False: 当前没有待合并任务
    """
    try:
        # 找出一条待合并的 session（READY_TO_COMPLETE）
        session = (
            UploadSession
            .select()
            .where(UploadSession.status == SESSION_STATUS_READY_TO_COMPLETE)
            .order_by(UploadSession.id)
            .first()
        )

        if not session:
            return False

        merge_one_session(session)
        return True

    except DoesNotExist:
        return False
    except Exception:
        traceback.print_exc()
        # 避免异常把 worker 顶死
        return False


def main():
    """
    简单的轮询式 worker：
      - 每 0.1 秒轮询一次数据库；
      - 一次只处理一条 READY_TO_COMPLETE 的任务；
      - 出错时打印 traceback 并继续轮询。
    """
    log_line("[merge_worker] Starting merge worker loop...")
    ensure_immich_root()

    try:
        while True:
            try:
                # 每次循环独立维护连接，避免长连接在 MySQL 端超时后产生莫名错误。
                if db.is_closed():
                    db.connect(reuse_if_open=True)

                handled = poll_and_merge_once()

            finally:
                # 每轮都尝试关闭连接，保持「短连接」模型，在小规模场景足够稳妥
                if not db.is_closed():
                    db.close()

            # 如果这轮没有任务，sleep 久一点；有任务则几乎立即处理下一条
            if not handled:
                time.sleep(0.1)
            else:
                # 这里也可以不 sleep，防止 CPU 打满的话可以给个极小的间隔
                time.sleep(0.01)

    except KeyboardInterrupt:
        log_line("\n[merge_worker] Stopped by user.")


if __name__ == "__main__":
    main()
