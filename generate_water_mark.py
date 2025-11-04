import json
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import qrcode
from crypter import encrypt_watermark, create_watermark_data


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


def add_watermark_to_image(original_image_path, name="梁振卓", user_number="2409840", base_date=None, base_time=None,
                           output_path="output_watermarked.jpg",
                           minute_offset=0):
    """
    给单张图片添加水印
    """

    today = datetime.today()
    now = today.time()
    month = str('{:0>2d}'.format(today.month))
    day = str('{:0>2d}'.format(today.day))
    hour = str('{:0>2d}'.format(now.hour))
    minute = str('{:0>2d}'.format(now.minute))

    if base_date is None:
        base_date = f"2025-{month}-{day}"
    if base_time is None:
        base_time = f"{hour}:{minute}"

    # 画布尺寸
    canvas_width = 1080
    canvas_height = 1920
    scale = canvas_width / 750

    # 创建白色背景
    result_image = Image.new('RGB', (canvas_width, canvas_height), 'white')
    draw = ImageDraw.Draw(result_image)

    # 加载原图
    original_image = Image.open(original_image_path)

    # 判断图片方向并旋转
    if original_image.width > original_image.height:
        # 横向图片，顺时针旋转90度
        original_image = original_image.rotate(-90, expand=True)

    # 检查是否需要裁剪
    need_crop = check_need_crop(original_image.width, original_image.height)

    if need_crop:
        # 裁剪图片
        crop_info = calculate_crop_area(original_image.width, original_image.height)
        cropped_image = original_image.crop((
            crop_info['sx'], crop_info['sy'],
            crop_info['sx'] + crop_info['sWidth'],
            crop_info['sy'] + crop_info['sHeight']
        ))
        resized_image = cropped_image.resize((canvas_width, canvas_height), Image.LANCZOS)
        result_image.paste(resized_image, (0, 0))
    else:
        # 直接缩放图片
        img_ratio = original_image.width / original_image.height
        canvas_ratio = canvas_width / canvas_height

        if abs(img_ratio - canvas_ratio) < 0.01:
            resized_image = original_image.resize((canvas_width, canvas_height), Image.LANCZOS)
            result_image.paste(resized_image, (0, 0))
        else:
            if img_ratio > canvas_ratio:
                draw_height = canvas_height
                draw_width = int(canvas_height * img_ratio)
                draw_x = (canvas_width - draw_width) // 2
                draw_y = 0
            else:
                draw_width = canvas_width
                draw_height = int(canvas_width / img_ratio)
                draw_x = 0
                draw_y = (canvas_height - draw_height) // 2

            resized_image = original_image.resize((draw_width, draw_height), Image.LANCZOS)
            result_image.paste(resized_image, (draw_x, draw_y))

    # 计算时间信息
    time_info = calculate_time(base_date, base_time, minute_offset)

    # 生成水印数据并加密
    watermark_data = create_watermark_data(
        time_info['timestamp'],
        int(user_number),
        name
    )
    encrypted_data = encrypt_watermark(watermark_data)

    # 生成二维码内容
    qr_data = json.dumps({
        "text": encrypted_data,
        "version": "v1.0"
    })

    # 生成二维码
    qr_size = 260
    qr_x = canvas_width - qr_size
    qr_y = canvas_height - qr_size

    # 绘制二维码背景（白色不透明）
    draw_rounded_rectangle(draw, qr_x, qr_y, qr_size, qr_size, 0, (255, 255, 0), alpha=255)

    # 生成并粘贴二维码
    qr_image = generate_qrcode(qr_data, qr_size)
    result_image.paste(qr_image, (qr_x, qr_y))

    # 绘制文字水印
    draw_text_watermark(draw, result_image, time_info, name, scale)

    # 保存结果
    if output_path:
        result_image.save(output_path, 'JPEG', quality=95)
        return output_path
    else:
        # 返回临时文件路径
        temp_path = f"watermarked_{int(datetime.now().timestamp())}.jpg"
        result_image.save(temp_path, 'JPEG', quality=95)
        return temp_path


def draw_text_watermark(draw, image, time_info, name, scale):
    """绘制文字水印信息"""
    canvas_width, canvas_height = image.size

    # 固定字号
    time_font_size = 75  # 时间字体大小
    name_font_size = 34  # 姓名字体大小
    date_font_size = 32  # 日期字体大小
    location_font_size = 32  # 位置字体大小

    # 加载字体
    font_path = "siyuansongti.ttf"  # 替换为你的字体文件路径
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

    location_icon = Image.open("location_icon.png")
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
