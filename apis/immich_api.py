import os
from datetime import datetime

import requests

from config import IMMICH_API_KEY, IMMICH_URL


class IMMICHApi:
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            'Accept': 'application/json',
            "x-api-key": IMMICH_API_KEY,
        }

    def get_statistics(self, start_time, end_time):
        # 获取资源统计
        payload = {
            "createdAfter": start_time,
            "createdBefore": end_time,
        }

        try:
            resp = requests.post(f"{IMMICH_URL}/search/statistics", json=payload, headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return int(data.get("total", 0))
        except Exception as e:
            return None

    def upload_to_immich_file(self, file_path: str):
        """上传文件到 Immich"""
        stats = os.stat(file_path)

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
            resp = requests.post(f"{IMMICH_URL}/assets", headers=self.headers, data=data, files=files)
            try:
                resp_json = resp.json()
                return resp_json.get("id", None)
            except Exception:
                return None
        finally:
            files['assetData'].close()
