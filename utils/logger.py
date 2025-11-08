import os
import threading
import fcntl
from datetime import datetime

from config import LOG_PATH

_lock = threading.Lock()


def log_line(*args):
    """线程+进程安全日志写入"""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    text = " ".join(str(a) for a in args)
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {text}\n"

    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            # 文件级互斥锁，防止多进程写入交叉
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(line)
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)
