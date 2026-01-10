import os
import time
from datetime import datetime
from io import BytesIO
from typing import List
from typing import Optional

import requests
from PIL import Image, UnidentifiedImageError

from config import (
    IMMICH_API_KEY,
    IMMICH_URL,
    IMMICH_LIBRARY_ID,
)
from utils.immich_utils import generate_device_asset_id
from utils.logger import log_line


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

    def scan_external_library(self) -> bool:
        url = f"{IMMICH_URL}/libraries/{IMMICH_LIBRARY_ID}/scan"
        try:
            resp = requests.post(
                url,
                headers=self.headers,
                json={"refreshModifiedFiles": False},
                timeout=30,
            )
        except Exception as e:
            log_line(f"[ERROR] 调用 scan_external_library 失败: {e}")
            return False

        if resp.status_code == 204:
            return True

        log_line(
            f"[ERROR] scan_external_library 状态异常: status={resp.status_code}, body={resp.text}"
        )
        return False

    def find_asset_by_original_path(self, original_path: str) -> Optional[str]:
        url = f"{IMMICH_URL}/search/metadata"
        payload = {
            "size": 1,
            "page": 1,
            "originalPath": original_path,
            "withDeleted": False,
        }

        try:
            resp = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30,
            )
        except Exception as e:
            log_line(f"[ERROR] find_asset_by_original_path 请求失败: {e}")
            return None

        if resp.status_code != 200:
            log_line(
                f"[ERROR] find_asset_by_original_path 状态异常: "
                f"status={resp.status_code}, body={resp.text}"
            )
            return None

        try:
            data = resp.json()
        except ValueError:
            log_line(f"[ERROR] find_asset_by_original_path JSON 解析失败")
            return None

        assets = data.get("assets") or {}
        items = assets.get("items") or []
        if not items:
            return None

        first = items[0]
        return first.get("id")

    def wait_asset_by_original_path(
            self,
            original_path: str,
            timeout: int = 60,
            interval: float = 2,
    ) -> Optional[str]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            asset_id = self.find_asset_by_original_path(original_path)
            if asset_id:
                log_line(
                    f"[INFO] Immich 已创建资源: originalPath={original_path}, asset_id={asset_id}"
                )
                return asset_id
            time.sleep(interval)

        log_line(f"[ERROR] 等待 Immich 创建资源超时: originalPath={original_path}")
        return None

    def put_assets_to_album(self, asset_id: str, album_id: str) -> bool:
        url = f"{IMMICH_URL}/albums/{album_id}/assets"
        payload = {"ids": [asset_id]}

        try:
            resp = requests.put(
                url,
                headers=self.headers,
                json=payload,
                timeout=30,
            )
        except Exception as e:
            log_line(f"[ERROR] put_assets_to_album 请求失败: {e}")
            return False

        if resp.status_code not in (200, 201):
            log_line(
                f"[ERROR] put_assets_to_album 状态异常: status={resp.status_code}, body={resp.text}"
            )
            return False

        return True

    def post_asset(
            self,
            file_path: str,
    ):
        if not os.path.isfile(file_path):
            log_line(f"[ERROR] 文件不存在: {file_path}")
            return False

        url = f"{IMMICH_URL}/assets"
        stats = os.stat(file_path)

        data = {
            'deviceAssetId': f'{file_path}-{stats.st_mtime}',
            'deviceId': 'python',
            'fileCreatedAt': datetime.fromtimestamp(stats.st_mtime),
            'fileModifiedAt': datetime.fromtimestamp(stats.st_mtime),
        }

        try:
            with open(file_path, "rb") as f:
                files = {
                    "assetData": f,
                }

                resp = requests.post(
                    url,
                    headers=self.headers,
                    data=data,
                    files=files,
                    timeout=120,
                )

                print(resp.json())
                return resp.json()
        except Exception as e:
            log_line(f"[ERROR] post_asset 请求失败: {e}")
            return False

    def upload_file_to_album(
            self,
            *,
            file_path: str,
            album_id: str,
    ) -> bool:
        """
        完整流程：
        1. hash 文件内容生成 deviceAssetId
        2. POST /assets（若已存在自动跳过）
        3. PUT /albums/{id}/assets
        """
        if not os.path.isfile(file_path):
            log_line(f"[ERROR] 文件不存在: {file_path}")
            return False

        device_asset_id = generate_device_asset_id(file_path)

        log_line(f"[INFO] 上传文件: {file_path}")
        log_line(f"[INFO] deviceAssetId: {device_asset_id}")

        ok = self.post_asset(file_path=file_path)

        if not ok:
            return False

        # Immich 中 asset_id == deviceAssetId（逻辑上）
        asset_id = ok.get("id")

        if not asset_id:
            log_line(f"[ERROR] 获取资产 ID 失败: {file_path}")
            return False

        if not self.put_assets_to_album(asset_id, album_id):
            log_line(
                f"[ERROR] 资产加入相册失败: asset={asset_id}, album={album_id}"
            )
            return False

        log_line(f"[INFO] 上传并加入相册成功: {file_path}")
        return True
