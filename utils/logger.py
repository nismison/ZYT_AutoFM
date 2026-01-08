import os
import threading
from datetime import datetime

from config import LOG_PATH, TZ

IS_WINDOWS = os.name == "nt"

_lock = threading.Lock()


def log_line(*args):
    """跨平台线程安全日志写入，不使用文件锁"""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    text = " ".join(str(a) for a in args)
    line = f"[{datetime.now(TZ):%Y-%m-%d %H:%M:%S}] {text}\n"

    if IS_WINDOWS:
        print(*args)
        return

    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
