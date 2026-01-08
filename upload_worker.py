import os
import shutil
import time
from datetime import datetime

from apis.immich_api import IMMICHApi
from config import IMMICH_TARGET_ALBUM_ID, IMMICH_EXTERNAL_CONTAINER_ROOT, IMMICH_EXTERNAL_HOST_ROOT, TZ
from db import UploadTask, UploadRecord
from utils.logger import log_line

MAX_RETRY = 3
FAILED_DIR = "storage/failed_uploads"


def ensure_failed_dir():
    if not os.path.exists(FAILED_DIR):
        os.makedirs(FAILED_DIR, exist_ok=True)


def task_worker():
    """
    后台异步任务：
    - 确认文件已在 External Library 根目录
    - 触发 External Library 扫描
    - 轮询 /search/metadata 等待 Immich 生成 asset
    - 加入指定相册
    - 写 UploadRecord
    """
    log_line("[INFO] 上传队列后台任务已启动")

    ensure_failed_dir()
    immich_api = IMMICHApi()

    while True:
        task = None

        try:
            # 取一条 pending 任务
            task = (
                UploadTask
                .select()
                .where(UploadTask.status == "pending")
                .order_by(UploadTask.created_at.asc())
                .first()
            )

            if not task:
                time.sleep(0.2)
                continue

            # 抢占任务
            rows = (
                UploadTask
                .update(status="processing", updated_at=datetime.now(TZ))
                .where(UploadTask.id == task.id, UploadTask.status == "pending")
                .execute()
            )
            if rows == 0:
                continue

            log_line(f"[INFO] 开始处理任务: id={task.id}, path={task.tmp_path}")

            # Step 1: 确认文件存在
            if not os.path.exists(task.tmp_path):
                log_line(f"[ERROR] 任务 {task.id} 对应文件不存在: {task.tmp_path}")
                (
                    UploadTask
                    .update(status="failed", updated_at=datetime.now(TZ), retry=task.retry + 1)
                    .where(UploadTask.id == task.id)
                    .execute()
                )
                continue

            # External Library 宿主机路径就是 tmp_path，无需移动
            host_path = task.tmp_path
            log_line(f"[INFO] 文件已在 External Library: {host_path}")

            # Immich 容器内部看到的 originalPath
            if task.external_rel_path:
                immich_original_path = os.path.join(
                    IMMICH_EXTERNAL_CONTAINER_ROOT,
                    task.external_rel_path,
                )
            else:
                # 兜底：如果旧任务没有 external_rel_path，用文件名拼
                immich_original_path = os.path.join(
                    IMMICH_EXTERNAL_CONTAINER_ROOT,
                    os.path.basename(host_path),
                )

            # Step 2: 触发 External Library 扫描
            if immich_api.scan_external_library():
                log_line("[INFO] External Library 扫描触发成功")
            else:
                raise RuntimeError("触发 Immich 扫描 External Library 失败")

            # Step 3: 轮询 originalPath 等待 Immich 建立 asset
            asset_id = immich_api.wait_asset_by_original_path(
                immich_original_path,
                timeout=60,
                interval=2.0,
            )
            log_line(f"[INFO] 扫描资产 originalPath={immich_original_path} → asset_id={asset_id}")

            if not asset_id:
                raise RuntimeError("在 Immich 中未找到对应资产（轮询超时）")

            # Step 4: 添加到相册
            ok = immich_api.put_assets_to_album(asset_id, IMMICH_TARGET_ALBUM_ID)
            if not ok:
                raise RuntimeError("添加资源到相册失败")
            log_line(f"[INFO] 已添加到相册: album_id={IMMICH_TARGET_ALBUM_ID}, asset_id={asset_id}")

            # Step 5: 写 UploadRecord
            try:
                UploadRecord.create(
                    oss_url="immich-external",
                    file_size=os.path.getsize(host_path),
                    upload_time=datetime.now(TZ),
                    original_filename=task.original_filename,
                    width=0,
                    height=0,
                    etag=task.etag,
                    fingerprint=task.fingerprint,
                    device_model=task.device,
                    thumb=None,
                    # 如果后面给 UploadRecord 加 asset_id 字段，可以写进去
                    # asset_id=asset_id,
                )
            except Exception as e:
                log_line(f"[ERROR] 写 UploadRecord 失败: {e}")

            # 标记任务完成
            (
                UploadTask
                .update(status="done", updated_at=datetime.now(TZ))
                .where(UploadTask.id == task.id)
                .execute()
            )

            log_line(f"[INFO] 任务完成: id={task.id}, asset_id={asset_id}")
            continue

        except Exception as e:
            # 只打印一行简洁的错误信息
            log_line(f"[ERROR] 任务执行失败: {e}")

            if task is not None:
                new_retry = task.retry + 1
                if new_retry >= MAX_RETRY:
                    # 多次失败，标记失败并尽量转存原始文件
                    src = getattr(task, "tmp_path", None)
                    if src and os.path.exists(src):
                        target = os.path.join(FAILED_DIR, f"{task.id}_{task.original_filename}")
                        try:
                            os.rename(src, target)
                            log_line(f"[ERROR] 多次失败，文件已转存到: {target}")
                        except Exception as move_err:
                            log_line(f"[ERROR] 转存失败文件出错: {move_err}")

                    (
                        UploadTask
                        .update(status="failed", retry=new_retry, updated_at=datetime.now(TZ))
                        .where(UploadTask.id == task.id)
                        .execute()
                    )
                else:
                    backoff = min(5 * new_retry, 20)
                    (
                        UploadTask
                        .update(status="pending", retry=new_retry, updated_at=datetime.now(TZ))
                        .where(UploadTask.id == task.id)
                        .execute()
                    )
                    log_line(
                        f"[ERROR] 任务失败，将重试({new_retry}/{MAX_RETRY})，延迟 {backoff}s"
                    )
                    time.sleep(backoff)

        time.sleep(0.1)


if __name__ == '__main__':
    task_worker()
