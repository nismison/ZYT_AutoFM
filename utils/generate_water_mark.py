import json
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import qrcode
from utils.crypter import create_watermark_data, encrypt_watermark


def calculate_time(base_date, base_time, minute_offset=0):
    """计算时间(基于基础时间+分钟偏移)"""
    base_datetime = datetime.strptime(f"{base_date} {base_time}", "%Y-%m-%d %H:%M")
    new_datetime = base_datetime + timedelta(minutes=minute_offset)

    # 使用正确的 weekday() 方法，注意：周一=0, 周日=6
    week_day = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    week = week_day[new_datetime.weekday()]

    return {
        "date": new_datetime.strftime("%Y-%m-%d"),
        "time": new_datetime.strftime("%H:%M"),
        "displayTime": new_datetime.strftime("%Y-%m-%d %H:%M"),
        "timestamp": int(new_datetime.timestamp()),
        "week": week,
        "fullDateTime": new_datetime.strftime("%Y-%m-%d %H:%M:%S")
    }


def generate_qrcode(data, size=300):
    """生成二维码"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img = qr_img.resize((size, size))

    return qr_img


def draw_rounded_rectangle(draw, x, y, width, height, radius, fill, alpha=128):
    """绘制半透明圆角矩形"""
    # 创建临时图层来绘制半透明效果
    temp_image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_image)

    # 绘制圆角矩形的主要矩形部分
    temp_draw.rectangle([radius, 0, width - radius, height], fill=(*fill, alpha))
    temp_draw.rectangle([0, radius, width, height - radius], fill=(*fill, alpha))

    # 绘制四个角
    temp_draw.ellipse([0, 0, radius * 2, radius * 2], fill=(*fill, alpha))
    temp_draw.ellipse([width - radius * 2, 0, width, radius * 2], fill=(*fill, alpha))
    temp_draw.ellipse([0, height - radius * 2, radius * 2, height], fill=(*fill, alpha))
    temp_draw.ellipse([width - radius * 2, height - radius * 2, width, height], fill=(*fill, alpha))

    # 将临时图层合并到原图
    main_image = draw._image
    main_image.paste(temp_image, (int(x), int(y)), temp_image)


def add_watermark_to_image(
        original_image_path,
        name="梁振卓",
        user_number="2409840",
        base_date=None,
        base_time=None,
        output_path=None,
        minute_offset=0):
    """
    给单张图片添加水印（高性能版本）
    - 全面禁用 LANCZOS，使用 BILINEAR（3~6 倍加速）
    - 最少 resize 次数
    - 缩放统一走 thumbnail（极快）
    - save 使用 quality=85（视觉无差异，但编码速度大幅提升）
    """

    # 时间准备
    today = datetime.today()
    if base_date is None:
        base_date = f"{today.year}-{today.month:02d}-{today.day:02d}"

    if base_time is None:
        now = today.time()
        base_time = f"{now.hour:02d}:{now.minute:02d}"

    # 固定画布
    canvas_width = 1080
    canvas_height = 1920
    scale = canvas_width / 750

    # 载入原图
    original = Image.open(original_image_path)

    # 横图自动旋转（原逻辑保留）
    if original.width > original.height:
        original = original.rotate(-90, expand=True)

    # 用 thumbnail 直接把原图限制到最大尺寸
    # thumbnail 自带等比例缩放，比 resize 快很多
    original.thumbnail((canvas_width, canvas_height), Image.BILINEAR)

    # 创建白底画布
    result = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(result)

    # 计算居中位置
    ow, oh = original.size
    dx = (canvas_width - ow) // 2
    dy = (canvas_height - oh) // 2
    result.paste(original, (dx, dy))

    # 时间计算
    time_info = calculate_time(base_date, base_time, minute_offset)

    # 生成并加密水印
    watermark_data = create_watermark_data(time_info['timestamp'], int(user_number), name)
    encrypted_data = encrypt_watermark(watermark_data)
    qr_payload = json.dumps({"text": encrypted_data, "version": "v1.0"})

    # 二维码放置位置与尺寸
    qr_size = 260
    qr_x = canvas_width - qr_size
    qr_y = canvas_height - qr_size

    # 二维码背景
    draw_rounded_rectangle(draw, qr_x, qr_y, qr_size, qr_size, 0, (255, 255, 0), alpha=255)

    # 生成二维码并贴上
    qr_img = generate_qrcode(qr_payload, qr_size)
    result.paste(qr_img, (qr_x, qr_y))

    # 文本水印
    draw_text_watermark(draw, result, time_info, name, scale)

    # 输出
    if output_path:
        result.save(output_path, "JPEG", quality=85, optimize=False)
        return output_path
    else:
        temp = f"watermarked_{int(datetime.now().timestamp())}.jpg"
        result.save(temp, "JPEG", quality=85, optimize=False)
        return temp


def draw_text_watermark(draw, image, time_info, name, scale):
    """绘制文字水印信息"""
    canvas_width, canvas_height = image.size

    # 固定字号
    time_font_size = 75  # 时间字体大小
    name_font_size = 34  # 姓名字体大小
    date_font_size = 32  # 日期字体大小
    location_font_size = 32  # 位置字体大小

    # 加载字体
    font_path = "static/siyuansongti.ttf"  # 替换为你的字体文件路径
    try:
        time_font = ImageFont.truetype(font_path, time_font_size)
        name_font = ImageFont.truetype(font_path, name_font_size)
        date_font = ImageFont.truetype(font_path, date_font_size)
        location_font = ImageFont.truetype(font_path, location_font_size)
    except:
        # 使用默认字体
        time_font = ImageFont.load_default()
        name_font = ImageFont.load_default()
        date_font = ImageFont.load_default()
        location_font = ImageFont.load_default()
        print("警告：字体加载失败，使用默认字体")

    # 第一行背景位置和尺寸（写死）
    first_line_x = 27  # 左边距
    first_line_y = 1674  # 距离底部 225px
    first_line_width = 480
    first_line_height = 107
    borderRadius = 15

    # 绘制第一行背景（半透明黑色）
    draw_rounded_rectangle(draw, first_line_x, first_line_y, first_line_width, first_line_height, borderRadius,
                           (0, 0, 0), alpha=102)

    # 时间文字位置（写死）
    time_text = time_info['time']
    time_x = first_line_x + 15
    time_y = first_line_y - 4

    draw.text((time_x, time_y), time_text, fill='white', font=time_font)

    # 姓名和日期位置（写死）
    name_date_x = first_line_x + 220

    name_text = name
    date_text = f"{time_info['date']} {time_info['week']}"

    # 姓名位置
    name_y = first_line_y + 5
    draw.text((name_date_x, name_y), name_text, fill='white', font=name_font)

    # 日期位置
    date_y = first_line_y + 50
    draw.text((name_date_x, date_y), date_text, fill='white', font=date_font)

    # 第二行位置信息（写死）
    location_x = 27
    location_y = 1794  # 距离底部 108px
    location_width = 302
    location_height = 60

    # 绘制位置背景（半透明黑色）
    draw_rounded_rectangle(draw, location_x, location_y, location_width, location_height, borderRadius, (0, 0, 0),
                           alpha=102)

    # 位置文字
    location_text = 'Q南宁中国锦园'
    location_text_x = location_x + 65
    location_text_y = location_y + 5

    draw.text((location_text_x, location_text_y), location_text, fill='white', font=location_font)

    # 位置图标 (使用emoji)
    icon_x = location_x + 22
    icon_y = location_y + 14

    location_icon = Image.open("static/location_icon.png")
    location_icon = location_icon.resize((30, 30))
    # 如果图标有透明通道，保持透明
    if location_icon.mode != 'RGBA':
        location_icon = location_icon.convert('RGBA')
    image.paste(location_icon, (icon_x, icon_y), location_icon)


def check_need_crop(width, height):
    """检查是否需要裁剪"""
    target_ratio = 9 / 16
    current_ratio = width / height
    tolerance = 0.01
    return abs(current_ratio - target_ratio) > tolerance


def calculate_crop_area(width, height):
    """计算裁剪区域"""
    target_ratio = 9 / 16
    if width / height > target_ratio:
        crop_width = height * target_ratio
        return {
            'sx': (width - crop_width) / 2,
            'sy': 0,
            'sWidth': crop_width,
            'sHeight': height,
            'dWidth': 1080,
            'dHeight': 1920
        }
    else:
        crop_height = width / target_ratio
        return {
            'sx': 0,
            'sy': (height - crop_height) / 2,
            'sWidth': width,
            'sHeight': crop_height,
            'dWidth': 1080,
            'dHeight': 1920
        }
