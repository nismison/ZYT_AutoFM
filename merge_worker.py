#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import time
import traceback

from config import (
    db,
    IMMICH_EXTERNAL_HOST_ROOT,
    FILE_STATUS_COMPLETED,
    SESSION_STATUS_READY_TO_COMPLETE,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_UPLOADING,
)
from db import File, UploadSession, UploadPart
from utils.logger import log_line


# =========================
# 路径相关工具函数
# =========================

def ensure_immich_root():
    """
    确保 IMMICH_EXTERNAL_HOST_ROOT 目录存在。
    """
    os.makedirs(IMMICH_EXTERNAL_HOST_ROOT, exist_ok=True)


def get_chunk_path(fingerprint: str, part_number: int) -> str:
    """
    构造分片文件路径。

    约定：所有分片直接放在 IMMICH_EXTERNAL_HOST_ROOT 根目录下，
    不使用子文件夹，命名规则例如：
        /immich-external-library/<fingerprint>_1.part
        /immich-external-library/<fingerprint>_2.part
    """
    filename = f"{fingerprint}_{part_number}.part"
    return os.path.join(IMMICH_EXTERNAL_HOST_ROOT, filename)


def get_final_file_path(file: File) -> str:
    """
    构造最终合并后的文件路径。

    约定：File.cos_key 存储的是「最终文件名」（不带目录），
    合并后的文件直接放到 IMMICH_EXTERNAL_HOST_ROOT 根目录下：
        /immich-external-library/<file.cos_key>
    """
    filename = file.cos_key  # 例如: "<fingerprint>_original.mp4"
    return os.path.join(IMMICH_EXTERNAL_HOST_ROOT, filename)


# =========================
# 合并逻辑
# =========================

def merge_one_session(session: UploadSession):
    file = session.file

    log_line(
        f"[INFO] [merge_worker] 开始合并: session_id={session.id}, "
        f"file_id={file.id}, fingerprint={file.fingerprint}"
    )

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
        # 没有任何分片，状态回滚，避免一直卡在 READY_TO_COMPLETE
        session.status = SESSION_STATUS_UPLOADING
        session.save()
        log_line(
            f"[INFO] [merge_worker] 无分片记录，回滚为 UPLOADING: session_id={session.id}"
        )
        return

    if len(parts) != session.total_chunks:
        # 分片数量不完整，回滚
        session.status = SESSION_STATUS_UPLOADING
        session.save()
        log_line(
            f"[INFO] [merge_worker] 分片数量不完整，回滚为 UPLOADING: "
            f"session_id={session.id}, got={len(parts)}, expected={session.total_chunks}"
        )
        return

    ensure_immich_root()
    final_path = get_final_file_path(file)
    tmp_path = final_path + ".tmp"

    try:
        with open(tmp_path, "wb") as out_f:
            for part in parts:
                chunk_path = get_chunk_path(file.fingerprint, part.part_number)
                if not os.path.exists(chunk_path):
                    # 分片文件丢失，终止本次合并并回滚状态
                    log_line(
                        f"[ERROR] [merge_worker] 分片文件缺失: {chunk_path}, "
                        f"session_id={session.id}, fingerprint={file.fingerprint}"
                    )
                    raise FileNotFoundError(chunk_path)

                with open(chunk_path, "rb") as in_f:
                    shutil.copyfileobj(in_f, out_f, length=1024 * 1024)

        os.replace(tmp_path, final_path)

        # 删除分片
        for part in parts:
            chunk_path = get_chunk_path(file.fingerprint, part.part_number)
            try:
                os.remove(chunk_path)
            except FileNotFoundError:
                pass

        # 更新状态
        file.status = FILE_STATUS_COMPLETED
        file.url = file.cos_key
        file.save()

        session.status = SESSION_STATUS_COMPLETED
        session.save()

        log_line(
            f"[INFO] [merge_worker] 合并成功: session_id={session.id}, "
            f"fingerprint={file.fingerprint}, final_path={final_path}"
        )
    except Exception as e:
        traceback.print_exc()
        log_line(
            f"[ERROR] [merge_worker] 合并失败: session_id={session.id}, "
            f"fingerprint={file.fingerprint}, error={e}"
        )

        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

        session.status = SESSION_STATUS_UPLOADING
        session.save()


def poll_and_merge_once() -> bool:
    try:
        total_ready = (
            UploadSession
            .select()
            .where(UploadSession.status == SESSION_STATUS_READY_TO_COMPLETE)
            .count()
        )

        # 仅在有任务时打一次统计日志
        if total_ready > 0:
            log_line(
                f"[INFO] [merge_worker] 当前待合并会话数: {total_ready}"
            )

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

    except Exception:
        traceback.print_exc()
        log_line("[ERROR] [merge_worker] poll_and_merge_once 发生异常")
        return False


def main():
    log_line("[INFO] [merge_worker] 后台合并任务已启动")
    ensure_immich_root()

    try:
        while True:
            try:
                if db.is_closed():
                    db.connect(reuse_if_open=True)

                handled = poll_and_merge_once()
            finally:
                if not db.is_closed():
                    db.close()

            # 没任务时稍微歇一会儿，有任务时快速处理下一条
            time.sleep(0.1 if not handled else 0.01)
    except KeyboardInterrupt:
        log_line("[INFO] [merge_worker] 收到 KeyboardInterrupt，停止合并任务")


if __name__ == "__main__":
    main()
