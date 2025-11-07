import os
from datetime import datetime
import requests
from config import IMMICH_API_KEY, IMMICH_URL


def upload_to_immich_file(file_path: str):
    """根据官方示例上传文件到 Immich"""
    stats = os.stat(file_path)

    headers = {
        'Accept': 'application/json',
        'x-api-key': IMMICH_API_KEY,
    }

    file_created = datetime.fromtimestamp(stats.st_mtime)
    data = {
        'deviceAssetId': f"{os.path.basename(file_path)}-{stats.st_mtime}",
        'deviceId': 'python',
        'fileCreatedAt': file_created,
        'fileModifiedAt': file_created,
        'isFavorite': 'false',
    }

    files = {
        'assetData': open(file_path, 'rb')
    }

    try:
        resp = requests.post(f"{IMMICH_URL}/assets", headers=headers, data=data, files=files)
        try:
            return resp.json()
        except Exception:
            return {"status": "fail"}
    finally:
        files['assetData'].close()