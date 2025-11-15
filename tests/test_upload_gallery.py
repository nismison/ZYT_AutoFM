import datetime
import hashlib
import io
import time

import pytest
import requests
from PIL import Image, ImageDraw, ImageFont

from apis.immich_api import IMMICHApi
from config import BASE_URL


@pytest.fixture(scope="module")
def immich_api():
    """提供 Immich API 实例"""
    return IMMICHApi()


@pytest.fixture
def test_image():
    """生成一张测试图片并返回内存对象及MD5"""
    img = Image.new("RGB", (800, 600), color=(80, 140, 220))
    draw = ImageDraw.Draw(img)
    text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        font = ImageFont.truetype("static/siyuansongti.ttf", 32)
    except Exception:
        font = ImageFont.load_default()

    # Pillow >=9.2 用 textbbox
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(text, font=font)

    draw.text(((800 - tw) / 2, (600 - th) / 2), text, fill="white", font=font)

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    img_bytes = buf.getvalue()
    etag = hashlib.md5(img_bytes).hexdigest()
    return buf, etag


def test_upload_to_gallery(immich_api, test_image):
    """测试 Flask 上传接口 + 检查上传记录 + Immich 验证 + 删除"""

    base_url = f"{BASE_URL}/upload_to_gallery"
    check_url = f"{BASE_URL}/api/check_uploaded"

    img_buf, etag = test_image
    files = {'file': ('pytest_test.jpg', io.BytesIO(img_buf.getvalue()), 'image/jpeg')}
    data = {'etag': etag}

    start = time.time()
    print(f"[INFO] 开始测试接口: {base_url}")

    # 上传到 Flask
    resp = requests.post(base_url, files=files, data=data)
    assert resp.status_code == 200, f"上传失败: HTTP {resp.status_code}"
    result = resp.json()
    assert result.get("success"), f"上传失败: {result}"
    asset_id = result.get("asset_id")
    print(f"[OK] 上传成功，资源ID: {asset_id}")

    # 检查 /api/check_uploaded 接口
    print("[INFO] 检查上传记录 ...")
    check_resp = requests.get(check_url, params={'etag': etag})
    assert check_resp.status_code == 200, f"check_uploaded 接口错误: HTTP {check_resp.status_code}"
    check_data = check_resp.json()
    assert check_data.get("success"), f"check_uploaded 执行失败: {check_data}"
    assert check_data.get("uploaded"), "上传记录未在数据库中找到"
    print(f"[OK] check_uploaded 验证通过 (etag={etag})")

    # 验证 Immich 中资源存在
    verified = immich_api.verify_asset(asset_id)
    assert verified, "Immich 验证失败"
    print("[OK] Immich 验证通过")

    # 删除资源
    deleted = immich_api.delete_assets([asset_id])
    assert deleted, "删除失败"
    print("[OK] 删除测试资源成功")

    elapsed = time.time() - start
    print(f"[SUCCESS] 测试完成 ✅ 用时 {elapsed:.2f}s")


if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
