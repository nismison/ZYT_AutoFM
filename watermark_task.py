import json
from datetime import datetime
from typing import Tuple

from PIL import Image, ImageDraw

from utils.crypter import create_watermark_data, encrypt_watermark
from utils.generate_water_mark import calculate_time, draw_rounded_rectangle, generate_qrcode, draw_text_watermark

try:
    from turbojpeg import TurboJPEG, TJPF_RGB

    _JPEG = TurboJPEG()
except Exception:
    _JPEG = None


# 这里假设你会把以下工具函数也放进本文件：
# - calculate_time
# - create_watermark_data
# - encrypt_watermark
# - draw_rounded_rectangle
# - generate_qrcode
# - draw_text_watermark
#
# from .watermark_utils import (
#     calculate_time,
#     create_watermark_data,
#     encrypt_watermark,
#     draw_rounded_rectangle,
#     generate_qrcode,
#     draw_text_watermark,
# )


def _load_and_fit_image_fast(image_path: str,
                             canvas_width: int = 1080,
                             canvas_height: int = 1920) -> Image.Image:
    """
    高性能加载图片并按 cover 模式适配到固定画布尺寸（不留白，中心裁剪）

    :param image_path: 原图文件路径
    :param canvas_width: 目标画布宽度
    :param canvas_height: 目标画布高度
    :returns: 已按 1080x1920 适配好的 PIL.Image 对象
    :raises keyError: 不涉及字典访问，不会抛出 keyError，异常时通常抛 OSError
    """
    if _JPEG is not None:
        with open(image_path, "rb") as f:
            buf = f.read()
        np_img = _JPEG.decode(buf, pixel_format=TJPF_RGB)
        img = Image.fromarray(np_img, mode="RGB")
    else:
        img = Image.open(image_path).convert("RGB")

    if img.width > img.height:
        img = img.rotate(-90, expand=True)

    src_w, src_h = img.size
    if src_w <= 0 or src_h <= 0:
        raise OSError("invalid source image size")

    scale_w = canvas_width / src_w
    scale_h = canvas_height / src_h
    scale = max(scale_w, scale_h)

    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    if new_w <= 0 or new_h <= 0:
        raise OSError("invalid scaled size")

    img = img.resize((new_w, new_h), Image.BILINEAR)

    left = (new_w - canvas_width) // 2
    top = (new_h - canvas_height) // 2
    right = left + canvas_width
    bottom = top + canvas_height

    img = img.crop((left, top, right, bottom))
    return img


def add_watermark_to_image(original_image_path: str,
                           name: str = "梁振卓",
                           user_number: str = "2409840",
                           base_date: str = None,
                           base_time: str = None,
                           output_path: str = None,
                           minute_offset: int = 0) -> str:
    """
    给单张图片添加水印（竖版 1080x1920，右下角二维码 + 文本水印）

    :param original_image_path: 原始图片路径
    :param name: 姓名，用于水印文本与加密数据
    :param user_number: 工号/用户编号，用于水印加密数据
    :param base_date: 基准日期 YYYY-MM-DD，None 时为当天
    :param base_time: 基准时间 HH:MM，None 时为当前时间
    :param output_path: 输出文件路径，为 None 时自动生成
    :param minute_offset: 在基准时间上偏移的分钟数，用于生成不同时间戳
    :returns: 最终生成的水印图片路径
    :raises keyError: 内部依赖函数如访问配置字典时可能抛出 keyError
    """
    today = datetime.today()

    if base_date is None:
        base_date = f"{today.year:04d}-{today.month:02d}-{today.day:02d}"

    if base_time is None:
        now = today.time()
        base_time = f"{now.hour:02d}:{now.minute:02d}"

    canvas_width = 1080
    canvas_height = 1920
    scale = canvas_width / 750.0

    base_image = _load_and_fit_image_fast(
        original_image_path,
        canvas_width=canvas_width,
        canvas_height=canvas_height
    )
    draw = ImageDraw.Draw(base_image)

    time_info = calculate_time(base_date, base_time, minute_offset)

    watermark_data = create_watermark_data(
        time_info["timestamp"],
        int(user_number),
        name
    )
    encrypted_data = encrypt_watermark(watermark_data)

    qr_data = json.dumps({
        "text": encrypted_data,
        "version": "v1.0"
    })

    qr_size = 260
    qr_x = canvas_width - qr_size
    qr_y = canvas_height - qr_size

    draw_rounded_rectangle(
        draw,
        qr_x,
        qr_y,
        qr_size,
        qr_size,
        0,
        (255, 255, 0),
        alpha=255
    )

    qr_image = generate_qrcode(qr_data, qr_size)
    base_image.paste(qr_image, (qr_x, qr_y))

    draw_text_watermark(
        draw,
        base_image,
        time_info,
        name,
        scale
    )

    if output_path is None:
        output_path = f"watermarked_{int(datetime.now().timestamp())}.jpg"

    base_image.save(output_path, "JPEG", quality=85, optimize=False)
    return output_path


def watermark_runner(args: Tuple[str, str, str, str, str, str]) -> str:
    """
    独立任务 runner：处理单张图片并输出到指定路径，供多进程池调用

    :param args: 六元组 (ori_path, name, user_number, base_date_str, time_str, out_file)
    :returns: 已生成水印图片的输出路径
    :raises keyError: 内部调用 add_watermark_to_image 时可能抛出 keyError
    """
    ori_path, name, user_number, base_date_str, time_str, out_file = args
    add_watermark_to_image(
        original_image_path=ori_path,
        name=name,
        user_number=user_number,
        base_date=base_date_str,
        base_time=time_str,
        output_path=out_file,
        minute_offset=0
    )
    return out_file
