import io
import hashlib
import datetime
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
        font = ImageFont.truetype("arial.ttf", 32)
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


def log(step: str, msg: str):
    """彩色输出"""
    COLORS = {
        "ok": "\033[92m",
        "warn": "\033[93m",
        "err": "\033[91m",
        "info": "\033[96m",
        "end": "\033[0m"
    }
    color = COLORS.get(step, COLORS["info"])
    print(f"{color}[{step.upper()}] {msg}{COLORS['end']}")


def test_upload_to_gallery(immich_api, test_image):
    """测试 Flask 上传 + Immich 验证 + 删除"""

    base_url = f"{BASE_URL}/upload_to_gallery"
    img_buf, etag = test_image
    files = {'file': ('pytest_test.jpg', io.BytesIO(img_buf.getvalue()), 'image/jpeg')}
    data = {'etag': etag}

    start = time.time()
    log("info", f"开始测试: {base_url}")

    # 上传到 Flask
    resp = requests.post(base_url, files=files, data=data)
    assert resp.status_code == 200, f"Flask 上传失败: HTTP {resp.status_code}"
    result = resp.json()
    assert result.get("success"), f"上传失败: {result}"
    asset_id = result.get("asset_id")
    log("ok", f"上传成功，资源ID: {asset_id}")

    # 验证 Immich 中资源存在
    verified = immich_api.verify_asset(asset_id)
    assert verified, "Immich 验证失败"
    log("ok", "Immich 验证通过")

    # 删除资源
    deleted = immich_api.delete_assets([asset_id])
    assert deleted, "删除失败"
    log("ok", "删除测试资源成功")

    elapsed = time.time() - start
    log("info", f"测试完成 ✅ 用时 {elapsed:.2f}s")


if __name__ == "__main__":
    # 允许独立运行
    pytest.main(["-v", __file__])
