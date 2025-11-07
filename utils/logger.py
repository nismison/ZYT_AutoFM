import os
from datetime import datetime

from config import LOG_PATH


def log_line(*args):
    """写入一行日志到指定文件"""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    text = " ".join(str(a) for a in args)
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {text}\n"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)
