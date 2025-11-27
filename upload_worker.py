import os
import shutil
import time
from datetime import datetime

from apis.immich_api import IMMICHApi
from config import IMMICH_TARGET_ALBUM_ID, IMMICH_EXTERNAL_CONTAINER_ROOT, IMMICH_EXTERNAL_HOST_ROOT
from db import UploadTask, UploadRecord
from utils.logger import log_line

MAX_RETRY = 3
FAILED_DIR = "storage/failed_uploads"


def ensure_failed_dir():
    if not os.path.exists(FAILED_DIR):
        os.makedirs(FAILED_DIR, exist_ok=True)


def task_worker():
    """后台异步：把文件从 tmp 挪到 External Library → 触发扫描 → 轮询拿 asset_id → 加相册 + 写记录"""
    log_line(f"[INFO] 后台上传线程已启动 (PID={os.getpid()})")

    ensure_failed_dir()
    immich_api = IMMICHApi()

    while True:
        task = None  # 关键：每轮循环先初始化，避免在 except 里引用未赋值变量

        try:
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
                .update(status="processing", updated_at=datetime.now())
                .where(UploadTask.id == task.id, UploadTask.status == "pending")
                .execute()
            )
            if rows == 0:
                continue

            # ========== Step 1: 把 tmp 文件挪到 External Library 目录 ==========
            if not task.external_rel_path:
                raise RuntimeError(f"任务 {task.id} 缺少 external_rel_path")

            host_target_path = os.path.join(IMMICH_EXTERNAL_HOST_ROOT, task.external_rel_path)
            os.makedirs(os.path.dirname(host_target_path), exist_ok=True)

            # 原子移动，避免扫描到半写文件
            shutil.move(task.tmp_path, host_target_path)
            log_line(f"[INFO] 文件已移动到 External Library: {host_target_path}")

            # Immich 容器内部看到的 originalPath
            immich_original_path = os.path.join(
                IMMICH_EXTERNAL_CONTAINER_ROOT,
                task.external_rel_path,
            )

            # ========== Step 2: 触发 External Library 扫描 ==========
            ok = immich_api.scan_external_library()
            if not ok:
                raise RuntimeError("触发 Immich 扫描 External Library 失败")

            # ========== Step 3: 轮询 originalPath 拿 asset_id ==========
            asset_id = immich_api.wait_asset_by_original_path(
                immich_original_path,
                timeout=60,
                interval=2.0,
            )
            log_line(f"[INFO] 扫描资产 originalPath={immich_original_path} → asset_id={asset_id}")

            if not asset_id:
                raise RuntimeError("在 Immich 中未找到对应资产（轮询超时）")

            # ========== Step 4: 添加到相册 ==========
            put_album = immich_api.put_assets_to_album(asset_id, IMMICH_TARGET_ALBUM_ID)
            log_line(f"[INFO] 添加到相册 -> {'成功' if put_album else '失败'}")

            # ========== Step 5: 写 UploadRecord ==========
            try:
                UploadRecord.create(
                    oss_url="immich-external",
                    file_size=os.path.getsize(host_target_path),
                    upload_time=datetime.now(),
                    original_filename=task.original_filename,
                    width=0,
                    height=0,
                    etag=task.etag,
                    fingerprint=task.fingerprint,
                    device_model=None,
                    thumb=None,
                    # 可以在这里加 asset_id 字段（如果表里有）
                    # asset_id=asset_id,
                )
            except Exception as e:
                log_line(f"[WARN] 写 UploadRecord 失败: {e}")

            # 更新任务状态
            (
                UploadTask
                .update(status="done", updated_at=datetime.now())
                .where(UploadTask.id == task.id)
                .execute()
            )

            # tmp_path 已经被 move，正常情况下这里不存在；保险起见再删一次
            try:
                if os.path.exists(task.tmp_path):
                    os.remove(task.tmp_path)
            except FileNotFoundError:
                pass

            log_line(f"[INFO] 任务完成: id={task.id}, asset_id={asset_id}")
            continue

        except Exception as e:
            import traceback
            traceback.print_exc()
            log_line(f"[ERROR] 任务异常: {e}")

            # 只有当本轮循环确实拿到了 task 时，才做重试逻辑
            if task is not None:
                new_retry = task.retry + 1
                if new_retry >= MAX_RETRY:
                    # 多次失败 → 把当前文件搬到失败目录（如果还在 tmp）
                    src = getattr(task, "tmp_path", None)
                    if src and os.path.exists(src):
                        target = os.path.join(FAILED_DIR, f"{task.id}_{task.original_filename}")
                        shutil.move(src, target)
                        log_line(f"[ERROR] 多次失败，已转存至: {target}")

                    (
                        UploadTask
                        .update(status="failed", retry=new_retry, updated_at=datetime.now())
                        .where(UploadTask.id == task.id)
                        .execute()
                    )
                else:
                    backoff = min(5 * new_retry, 20)
                    (
                        UploadTask
                        .update(status="pending", retry=new_retry, updated_at=datetime.now())
                        .where(UploadTask.id == task.id)
                        .execute()
                    )
                    log_line(
                        f"[ERROR] 上传失败，将重试({new_retry}/{MAX_RETRY})，延迟 {backoff}s: {getattr(task, 'tmp_path', '')}"
                    )
                    time.sleep(backoff)

        time.sleep(0.1)


if __name__ == '__main__':
    task_worker()
