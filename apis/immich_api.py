import os
from datetime import datetime
from io import BytesIO
from typing import List

import requests
from PIL import Image, UnidentifiedImageError

from config import IMMICH_API_KEY, IMMICH_URL


class IMMICHApi:
    def __init__(self):
        self.headers = {
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
            resp = requests.post(f"http://immich_server:2283/api/search/statistics", json=payload, headers=self.headers,
                                 timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return int(data.get("total", 0))
        except Exception as e:
            print(f"❌ 获取统计数据失败: {e}")
            return None

    def upload_to_immich_file(self, file_path: str):
        """上传文件到 Immich"""
        stats = os.stat(file_path)
        current_time = datetime.now().isoformat()

        data = {
            'deviceAssetId': f"{os.path.basename(file_path)}-{stats.st_mtime}",
            'deviceId': 'python',
            'fileCreatedAt': current_time,
            'fileModifiedAt': current_time,
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

    def verify_asset(self, asset_id: str):
        """验证immich资源"""
        try:
            resp = requests.get(f"{IMMICH_URL}/assets/{asset_id}/original", headers=self.headers)
            try:
                Image.open(BytesIO(resp.content)).verify()
                return True
            except UnidentifiedImageError:
                print("❌ 无法识别图片（不是合法图片格式）")
                return False
            except Exception as e:
                print(f"❌ 图片验证失败: {e}")
                return False
        except Exception as e:
            print(f"❌ 获取原图失败: {e}")
            return False

    def delete_assets(self, asset_ids: List[str]):
        """删除immich资源"""
        data = {
            'ids': asset_ids
        }

        try:
            resp = requests.delete(f"{IMMICH_URL}/assets", json=data, headers=self.headers)

            if resp.status_code == 204:
                print("✅ 删除成功")
                return True
            else:
                print(f"❌ 删除失败: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ 获取原图失败: {e}")
            return False

    def put_assets_to_album(self, asset_id: str, album_id: str):
        """把资源添加到文件夹"""
        data = {
            'ids': [asset_id]
        }

        try:
            resp = requests.put(f"{IMMICH_URL}/albums/{album_id}/assets", json=data, headers=self.headers)

            print(resp.status_code)
            if resp.status_code == 200:
                print(resp.json())
                if resp.json()[0].get("success", False):
                    print("✅ 添加成功")
                    return True
                else:
                    print(f"❌ 添加失败: {resp.json()[0].get('error', '未知错误')}")
                    return False
            else:
                print(f"❌ 添加失败: Status Code -> {resp.status_code}")
                return False
        except Exception as e:
            print(f"❌ 添加失败: Exception -> {e}")
            return False
