import datetime
import io
import json

import pytest
import requests
from PIL import Image, ImageDraw, ImageFont
from pyzbar.pyzbar import decode as decode_qr

from config import BASE_URL
from utils.crypter import decrypt_with_string_key  # ✅ 你的解密方法

# Flask 接口地址
TEST_URL = f"{BASE_URL}/upload_with_watermark"


def generate_test_image(text: str, size=(200, 400), color=(80, 140, 220)):
    """生成一张带文字的测试图片（保存在内存）"""
    img = Image.new("RGB", size, color=color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("static/siyuansongti.ttf", 32)
    except Exception:
        font = ImageFont.load_default()
    draw.text((20, 20), text, fill="white", font=font)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


def verify_image_basic(url: str):
    """验证图片可访问且为合法 JPEG"""
    resp = requests.get(url)
    assert resp.status_code == 200, f"图片无法访问: {url}"
    img = Image.open(io.BytesIO(resp.content))
    img.verify()
    return resp.content


def decode_qrcode_from_bytes(img_bytes: bytes):
    """解析二维码数据"""
    img = Image.open(io.BytesIO(img_bytes))
    decoded = decode_qr(img)
    if not decoded:
        return None
    try:
        data_str = decoded[0].data.decode("utf-8")
        return data_str
    except Exception:
        return None


def try_decrypt_qrdata(qr_data: str):
    """
    从二维码JSON中提取text字段 → 解密 → 解析为字典
    如果任一步失败返回None
    """
    try:
        qr_json = json.loads(qr_data)
        encrypted_text = qr_json.get("text")
        if not encrypted_text:
            return None
        return decrypt_with_string_key(encrypted_text)
    except Exception:
        return None


def upload_images(merge: bool):
    """上传9张测试图片"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    now = datetime.datetime.now().strftime("%H:%M")
    name = "梁振卓"
    user_number = "2409840"

    files = []
    for i in range(9):
        buf = generate_test_image(f"测试图 {i + 1}")
        files.append(("file", (f"test_{i + 1}.jpg", buf, "image/jpeg")))

    data = {
        "name": name,
        "user_number": user_number,
        "base_date": today,
        "base_time": now,
        "merge": str(merge).lower(),
    }

    print(f"\n[INFO] 上传 9 张测试图片 (merge={merge}) ...")
    resp = requests.post(TEST_URL, files=files, data=data)
    assert resp.status_code == 200, f"接口异常 HTTP {resp.status_code}"
    result = resp.json()
    assert result.get("success"), f"接口执行失败: {result}"
    return result, name, user_number


@pytest.mark.parametrize("merge", [False, True])
def test_upload_with_watermark_and_qrcode(merge):
    """测试 /upload_with_watermark 接口 + 二维码解密验证"""
    result, name, user_number = upload_images(merge)
    oss_urls = result.get("oss_urls", [])
    count = result.get("count")

    print(f"[INFO] 返回 {count} 张图片 (merge={merge})")
    assert len(oss_urls) >= 1

    for url in oss_urls:
        print(f"[CHECK] 验证图片 {url}")
        img_bytes = verify_image_basic(url)

        if not merge:
            # 解析二维码
            qr_data = decode_qrcode_from_bytes(img_bytes)
            assert qr_data, f"未检测到二维码: {url}"

            # 解析 JSON 并解密 text 字段
            decrypted_dict = try_decrypt_qrdata(qr_data)
            assert decrypted_dict, f"二维码数据无法解密或格式错误: {qr_data}"

            # 验证字段
            n = decrypted_dict.get("n")
            s = str(decrypted_dict.get("s"))
            assert n == name, f"二维码字段 n 不匹配: {n} != {name}"
            assert s == user_number, f"二维码字段 s 不匹配: {s} != {user_number}"

            print(f"[OK] 二维码验证通过 → n={n}, s={s}")

    print(f"[SUCCESS] merge={merge} 测试通过 ✅ 共验证 {len(oss_urls)} 张图片。")


if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
