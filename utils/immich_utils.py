import os
import uuid

# 固定 namespace，保证跨进程 / 跨机器一致
IMMICH_ASSET_NAMESPACE = uuid.UUID("2f5a9c6e-4c3b-4b1f-9f6a-9c6c1b7e8a01")


def generate_device_asset_id(file_path: str) -> str:
    """
    基于文件生成稳定 UUID（UUID v5）
    文件内容不变 → UUID 不变
    """
    stat = os.stat(file_path)

    identity = f"{file_path}:{stat.st_size}:{int(stat.st_mtime)}"

    return str(uuid.uuid5(IMMICH_ASSET_NAMESPACE, identity))
