import os
import random


class Utils:
    @staticmethod
    def get_random_template_file(category):
        """随机返回TemplatePic下指定目录的随机文件"""
        target_dir = f"TemplatePic/{category}"

        if not os.path.isdir(target_dir):
            return None

        files = [f for f in os.listdir(target_dir)
                 if os.path.isfile(os.path.join(target_dir, f)) and not f.startswith('.')]

        return os.path.join(target_dir, random.choice(files)) if files else None
