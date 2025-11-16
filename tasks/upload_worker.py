import os
import shutil
import time
from datetime import datetime

from apis.immich_api import IMMICHApi
from db import UploadTask, UploadRecord
from utils.logger import log_line

MAX_RETRY = 3
FAILED_DIR = "storage/failed_uploads"


def ensure_failed_dir():
    if not os.path.exists(FAILED_DIR):
        os.makedirs(FAILED_DIR, exist_ok=True)


def task_worker():
    """后台异步上传 Immich（自动重试 + 写入 UploadRecord + 失败转存）"""
    log_line(f"[INFO] 后台上传线程已启动 (PID={os.getpid()})")

    ensure_failed_dir()
    immich_api = IMMICHApi()

    while True:
        try:
            task = (UploadTask
                    .select()
                    .where(UploadTask.status == "pending")
                    .order_by(UploadTask.created_at.asc())
                    .first())

            if not task:
                time.sleep(0.2)
                continue

            # 抢占任务
            rows = (UploadTask
                    .update(status="processing", updated_at=datetime.now())
                    .where(UploadTask.id == task.id,
                           UploadTask.status == "pending")
                    .execute())

            if rows == 0:
                continue

            # ---- 上传开始 ----
            asset_id = immich_api.upload_to_immich_file(task.tmp_path)
            log_line(f"上传Immich -> asset_id: {asset_id}")

            # 添加到相册
            put_album = immich_api.put_assets_to_album(asset_ids=[asset_id],
                                                       album_ids=["fa588b80-6b40-4607-8d6c-cd90101db9e9"])
            log_line(f"添加到相册 -> {'成功' if put_album else '失败'}")

            if asset_id:
                # ========== 上传成功：写入 UploadRecord ==========
                try:
                    UploadRecord.create(
                        oss_url="immich",  # 你这里可以改为实际地址
                        file_size=os.path.getsize(task.tmp_path),
                        upload_time=datetime.now(),
                        original_filename=task.original_filename,
                        width=0,  # 如需真实宽高你可以提取
                        height=0,
                        etag=task.etag,
                        device_model=None,
                        thumb=None,
                    )
                except Exception as e:
                    log_line(f"[INFO] 写 UploadRecord 失败: {e}")

                # 更新任务状态
                UploadTask.update(
                    status="done",
                    updated_at=datetime.now()
                ).where(UploadTask.id == task.id).execute()

                # 删除临时文件
                try:
                    os.remove(task.tmp_path)
                except FileNotFoundError:
                    pass

                log_line(f"[INFO] 上传成功: {task.tmp_path}")
                continue

            # ---- 上传失败：自动重试 ----
            new_retry = task.retry + 1

            if new_retry >= MAX_RETRY:
                # 多次失败 → 转存失败文件
                target = os.path.join(FAILED_DIR,
                                      f"{task.id}_{task.original_filename}")
                shutil.move(task.tmp_path, target)

                UploadTask.update(
                    status="failed",
                    retry=new_retry,
                    updated_at=datetime.now()
                ).where(UploadTask.id == task.id).execute()

                log_line(f"[ERROR] 多次失败，已转存至: {target}")
            else:
                backoff = min(5 * new_retry, 20)

                UploadTask.update(
                    status="pending",
                    retry=new_retry,
                    updated_at=datetime.now()
                ).where(UploadTask.id == task.id).execute()

                log_line(
                    f"[ERROR] 上传失败，将重试({new_retry}/{MAX_RETRY})，延迟 {backoff}s: {task.tmp_path}"
                )

                time.sleep(backoff)

        except Exception as e:
            import traceback
            traceback.print_exc()
            log_line(f"[ERROR] 异常: {e}")

        time.sleep(0.1)
