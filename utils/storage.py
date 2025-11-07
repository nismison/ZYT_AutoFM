import os
import random
import string
from config import BASE_URL


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
