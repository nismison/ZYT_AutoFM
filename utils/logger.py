import os
import threading
from datetime import datetime
from config import LOG_PATH

# 检测平台
IS_WINDOWS = os.name == "nt"

# Windows 无 fcntl，Linux 才加载
if not IS_WINDOWS:
    import fcntl

_lock = threading.Lock()


def log_line(*args):
    """跨平台线程/进程安全日志写入"""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    text = " ".join(str(a) for a in args)
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {text}\n"

    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            if not IS_WINDOWS:
                fcntl.flock(f, fcntl.LOCK_EX)
            f.write(line)
            f.flush()
            if not IS_WINDOWS:
                fcntl.flock(f, fcntl.LOCK_UN)
