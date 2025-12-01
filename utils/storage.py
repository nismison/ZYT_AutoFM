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
    try:
        if sub_category:
            target_dir = f"TemplatePic/{category}/{sub_category}"
        else:
            target_dir = f"TemplatePic/{category}"

        if not os.path.isdir(target_dir):
            return None

        files = [f for f in os.listdir(target_dir)
                 if os.path.isfile(os.path.join(target_dir, f)) and not f.startswith('.')]

        return os.path.join(target_dir, random.choice(files)) if files else None
    except Exception:
        return None


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
    去除所有 Stream 层 creation_time，并写入带时区的容器层 creation_time，
    确保 Immich 使用本地时区(+08:00)而不是 UTC。

    :param src_path: 输入视频文件
    :param dst_path: 输出视频文件（写入新 metadata 后）
    :returns: None
    :raises RuntimeError: ffmpeg 执行失败时抛出异常
    """
    now = datetime.now().astimezone()
    timestamp = now.isoformat(timespec="seconds")  # 例如 2025-11-14T12:43:49+08:00

    cmd = [
        "ffmpeg",
        "-i", src_path,

        # 删除所有 metadata（关键，必须保留）
        "-map", "0",
        "-map_metadata", "-1",

        # 写入容器层 metadata（Immich 会使用这个）
        "-metadata", f"creation_time={timestamp}",
        "-metadata", f"date={timestamp}",

        # 不重编码（极快）
        "-c", "copy",

        dst_path,
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg 修改视频 metadata 失败: {proc.stderr.decode(errors='ignore')}"
        )


def find_review_dir_by_filename(filename):
    """
    在 pending 下递归查找文件名，并返回该文件所在的目录绝对路径。

    :param filename: 文件名，例如 "8ac82f3aa9d8c1bd91e.jpg"
    :returns: 目录绝对路径，如 "storage/reviews/pending/aaa/bbb"
    :raises FileNotFoundError: 没找到对应文件时抛错
    """
    base = os.path.join("storage", "reviews", "pending")

    for root, dirs, files in os.walk(base):
        if filename in files:
            return root

    raise FileNotFoundError(f"未找到文件: {filename}")
