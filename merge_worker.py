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
    SESSION_STATUS_COMPLETED, SESSION_STATUS_UPLOADING,
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
    file = session.file

    print(f"[merge_worker] Merging session id={session.id}, "
          f"file_id={file.id}, fingerprint={file.fingerprint}")

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
    print(f"[merge_worker] Found {len(parts)} parts for session id={session.id}, "
          f"expected={session.total_chunks}")

    if not parts:
        print(f"[merge_worker] No parts found, mark session back to UPLOADING.")
        session.status = SESSION_STATUS_UPLOADING
        session.save()
        return

    if len(parts) != session.total_chunks:
        print(f"[merge_worker] Incomplete parts: got={len(parts)}, "
              f"expected={session.total_chunks}, mark back to UPLOADING.")
        session.status = SESSION_STATUS_UPLOADING
        session.save()
        return

    ensure_immich_root()
    final_path = get_final_file_path(file)
    tmp_path = final_path + ".tmp"

    print(f"[merge_worker] Start merging to {final_path}")

    try:
        with open(tmp_path, "wb") as out_f:
            for part in parts:
                chunk_path = get_chunk_path(file.fingerprint, part.part_number)
                print(f"[merge_worker]  Merging chunk: {chunk_path}")

                if not os.path.exists(chunk_path):
                    print(f"[merge_worker]  Chunk missing: {chunk_path}, abort.")
                    raise FileNotFoundError(chunk_path)

                with open(chunk_path, "rb") as in_f:
                    shutil.copyfileobj(in_f, out_f, length=1024 * 1024)

        os.replace(tmp_path, final_path)

        # 删除分片
        for part in parts:
            chunk_path = get_chunk_path(file.fingerprint, part.part_number)
            try:
                os.remove(chunk_path)
                print(f"[merge_worker]  Deleted chunk: {chunk_path}")
            except FileNotFoundError:
                pass

        # 更新状态
        file.status = FILE_STATUS_COMPLETED
        file.url = file.cos_key
        file.save()

        session.status = SESSION_STATUS_COMPLETED
        session.save()

        print(f"[merge_worker] Merge success for file fingerprint={file.fingerprint}")
    except Exception as e:
        traceback.print_exc()
        print(f"[merge_worker] Merge failed: {e}")

        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

        session.status = SESSION_STATUS_UPLOADING
        session.save()


def poll_and_merge_once() -> bool:
    try:
        # 这里打印一下数据库里 READY_TO_COMPLETE 的个数
        total_ready = (
            UploadSession
            .select()
            .where(UploadSession.status == SESSION_STATUS_READY_TO_COMPLETE)
            .count()
        )
        print(f"[merge_worker] READY_TO_COMPLETE sessions count = {total_ready}")

        session = (
            UploadSession
            .select()
            .where(UploadSession.status == SESSION_STATUS_READY_TO_COMPLETE)
            .order_by(UploadSession.id)
            .first()
        )

        if not session:
            print("[merge_worker] No READY_TO_COMPLETE session found this round.")
            return False

        merge_one_session(session)
        return True

    except Exception:
        traceback.print_exc()
        return False


def main():
    print("[merge_worker] Starting merge worker loop...")
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

            if not handled:
                time.sleep(0.1)
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n[merge_worker] Stopped by user.")


if __name__ == "__main__":
    main()
