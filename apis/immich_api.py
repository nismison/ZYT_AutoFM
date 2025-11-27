import time
from io import BytesIO
from typing import List

import requests
from PIL import Image, UnidentifiedImageError

from config import (
    IMMICH_API_KEY,
    IMMICH_URL,
    IMMICH_LIBRARY_ID,
    IMMICH_TARGET_ALBUM_ID,
)
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
        """触发 External Library 扫描，仅返回 True/False，不抛异常"""
        url = f"{IMMICH_URL}/libraries/{IMMICH_LIBRARY_ID}/scan"
        try:
            resp = requests.post(
                url,
                headers=self.headers,
                json={"refreshModifiedFiles": False},
                timeout=30,
            )
        except Exception as e:
            log_line(f"[ERROR] 调用 scan_external_library 请求异常: {e}")
            return False

        # Immich 这里规范是 204 No Content 为成功
        if resp.status_code == 204:
            log_line("[INFO] scan_external_library 调用成功 (204)")
            return True

        log_line(
            f"[ERROR] scan_external_library 调用失败: status={resp.status_code}, body={resp.text}"
        )
        return False

    def find_asset_by_original_path(self, original_path: str):
        """通过 originalPath 查找资产，返回 asset_id 或 None"""
        url = f"{IMMICH_URL}/api/search/metadata"
        payload = {
            "size": 1,
            "page": 1,
            "originalPath": original_path,
            "withDeleted": False,
        }
        resp = requests.post(url, headers=self.headers, json=payload, timeout=30)

        if resp.status_code != 200:
            log_line(
                f"[ERROR] find_asset_by_original_path 失败: status={resp.status_code}, body={resp.text}"
            )
            return None

        data = resp.json()
        assets = data.get("assets", {}).get("items") or data.get("assets", [])
        if not assets:
            return None

        return assets[0].get("id")

    def wait_asset_by_original_path(
            self,
            original_path: str,
            timeout: int = 60,
            interval: float = 2.0,
    ):
        """轮询等待 Immich 建立资产，超时返回 None，不抛异常"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            asset_id = self.find_asset_by_original_path(original_path)
            if asset_id:
                log_line(
                    f"[INFO] wait_asset_by_original_path 命中: originalPath={original_path}, asset_id={asset_id}"
                )
                return asset_id
            time.sleep(interval)

        log_line(
            f"[WARN] wait_asset_by_original_path 超时: originalPath={original_path}"
        )
        return None

    def put_assets_to_album(self, asset_id: str, album_id: str = None) -> bool:
        """把单个 asset 加入相册，返回 True/False，并打印详细错误日志"""
        if album_id is None:
            album_id = IMMICH_TARGET_ALBUM_ID

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
            log_line(f"[ERROR] put_assets_to_album 请求异常: {e}")
            return False

        # Immich API 文档：200 返回一个数组 [{ id, success, error? }]
        # https://api.immich.app/endpoints/albums/addAssetsToAlbum :contentReference[oaicite:1]{index=1}
        status = resp.status_code

        try:
            data = resp.json()
        except ValueError:
            data = None

        if status not in (200, 201):
            log_line(
                f"[ERROR] put_assets_to_album 失败: status={status}, body={data or resp.text}"
            )
            return False

        # data 形如: [{"id": "...uuid...", "success": true/false, "error": "duplicate"/...}]
        if isinstance(data, list):
            failed = [item for item in data if not item.get("success", False)]
            if failed:
                for item in failed:
                    log_line(
                        f"[ERROR] put_assets_to_album 单条失败: "
                        f"id={item.get('id')}, error={item.get('error')}"
                    )
                return False

        log_line(
            f"[INFO] put_assets_to_album 成功: album_id={album_id}, asset_id={asset_id}, status={status}"
        )
        return True
