import os
import time
from collections import deque

from flask import Blueprint, render_template, Response

from config import LOG_PATH

bp = Blueprint("log_viewer", __name__)


@bp.route("/logs")
def index():
    return render_template("log_viewer.html")


@bp.route("/stream")
def stream():
    """先输出文件末尾500行，再实时推送新增内容"""
    def generate():
        # 等待文件出现
        while not os.path.exists(LOG_PATH):
            time.sleep(1)

        # 打开文件并准备读取
        with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            # 取最后500行
            last_lines = deque(f, maxlen=500)
            for line in last_lines:
                yield f"data: {line.rstrip()}\n\n"

            # 实时监听
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")