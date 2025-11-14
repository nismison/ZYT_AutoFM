import os
import random
import string
import subprocess
from datetime import datetime

from PIL import Image, ExifTags

from config import BASE_URL


def get_local_iso8601():
    """
    返回带时区并带冒号的 ISO8601 时间，例如：
    2025-11-13T10:20:00+08:00
    """
    now = datetime.now().astimezone()
    # 先拿到 +0800
    tz_raw = now.strftime("%z")  # "+0800"
    # 插入冒号 → "+08:00"
    tz_fixed = tz_raw[:3] + ":" + tz_raw[3:]
    return now.strftime("%Y-%m-%dT%H:%M:%S") + tz_fixed


def generate_random_suffix(length: int = 8) -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def get_image_url(image_id: str, image_type: str = 'gallery') -> str:
    return f"{BASE_URL}/api/image/{image_type}/{image_id}"


def get_random_template_file(category, sub_category=None):
    """随机返回TemplatePic下指定目录的随机文件"""
    if sub_category:
        target_dir = f"TemplatePic/{category}/{sub_category}"
    else:
        target_dir = f"TemplatePic/{category}"

    if not os.path.isdir(target_dir):
        return None

    files = [f for f in os.listdir(target_dir)
             if os.path.isfile(os.path.join(target_dir, f)) and not f.startswith('.')]

    return os.path.join(target_dir, random.choice(files)) if files else None


def update_exif_datetime(image_path: str):
    """用 Pillow 修改 JPEG 图片 EXIF 时间为当前时间"""
    try:
        img = Image.open(image_path)
        exif = img.getexif()
        now_str = datetime.now().strftime("%Y:%m:%d %H:%M:%S")

        # 找到 DateTime、DateTimeOriginal、DateTimeDigitized 的 tag ID
        TAGS = {v: k for k, v in ExifTags.TAGS.items()}
        for tag_name in ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]:
            tag_id = TAGS.get(tag_name)
            if tag_id:
                exif[tag_id] = now_str

        img.save(image_path, exif=exif)
        print(f"EXIF 时间更新为 {now_str}")
    except Exception as e:
        print(f"EXIF 更新时间失败: {e}")


def fix_video_metadata(src_path: str, dst_path: str) -> None:
    """
    重写视频 metadata，使 Immich 能正确识别本地时区时间。
    方案：清除所有 Stream 层的 creation_time，强制 Immich fallback
         到 Container 层的 creation_time（可写入带时区信息）

    :param src_path: 输入视频路径
    :param dst_path: 输出视频路径
    :returns: None
    :raises RuntimeError: ffmpeg 执行失败时抛出
    """
    now = datetime.now().astimezone()
    timestamp = now.isoformat(timespec="seconds")

    cmd = [
        "ffmpeg",
        "-i", src_path,

        # 删除 Stream 层 creation_time（关键）
        "-metadata:s:v:0", "creation_time=",
        "-metadata:s:a:0", "creation_time=",

        # Container 层写入带时区时间
        "-metadata", f"creation_time={timestamp}",
        "-metadata", f"date={timestamp}",

        "-codec", "copy",
        dst_path,
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg 修改视频 metadata 失败: {proc.stderr.decode(errors='ignore')}"
        )
