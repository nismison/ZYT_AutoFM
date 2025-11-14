from datetime import datetime
from typing import Optional

from flask import Flask, request
from flask_cors import CORS

from config import IS_DEV
from db import init_database_connection
from routes import register_blueprints
from utils.logger import log_line


# ==================================================
# 工具函数
# ==================================================
def now() -> str:
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")


def truncate(text, limit=500):
    if not text:
        return ""
    return text[:limit] + ("...（已截断）" if len(text) > limit else "")


def summarize_by_type(content_type, data):
    """根据类型生成内容概要"""
    text = data or ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")

    if not content_type:
        return truncate(text)

    ct = content_type.lower()
    if "image" in ct:
        return "[图片]"
    if "video" in ct:
        return "[视频]"
    if "audio" in ct:
        return "[音频]"
    if "multipart/form-data" in ct or "octet-stream" in ct:
        return "[文件]"
    return truncate(text)


def is_textual_content(content_type: Optional[str]) -> bool:
    if not content_type:
        return True
    ct = content_type.lower()
    if ct.startswith("text/"):
        return True
    textual_prefixes = (
        "application/json",
        "application/javascript",
        "application/xml",
        "application/xhtml+xml",
        "application/x-www-form-urlencoded",
    )
    return ct.startswith(textual_prefixes)


def should_skip_logging(path: str) -> bool:
    """过滤不需要记录日志的路径"""
    skip_prefixes = ("/logs", "/stream", "/api/image", "/send_notify")
    return any(path.startswith(p) for p in skip_prefixes)


# ==================================================
# Flask 应用
# ==================================================
def create_app() -> Flask:
    app = Flask(__name__)

    # 初始化数据库连接
    with app.app_context():
        init_database_connection()

    @app.before_request
    def log_request():
        """请求前日志记录"""
        if should_skip_logging(request.path):
            return

        content_type = request.content_type or ""
        if "multipart/form-data" in content_type:
            form_fields = {k: v for k, v in request.form.items()}
            file_fields = {k: "[文件]" for k in request.files}
            body = {"form": form_fields, "files": file_fields}
        else:
            data = None
            if is_textual_content(content_type):
                try:
                    data = request.get_data(as_text=True)
                except UnicodeDecodeError:
                    data = request.get_data()
            body = summarize_by_type(content_type, data)

        log_line("=" * 60)
        log_line(f"请求路径: {request.path}")
        log_line(f"请求数据: {body}")

    @app.after_request
    def log_response(response):
        """响应后日志记录"""
        if should_skip_logging(request.path):
            return response

        content_type = response.content_type or ""
        if "text/event-stream" in content_type:
            body = "[SSE流]"
        elif getattr(response, "direct_passthrough", False):
            body = "[直接透传响应]"
        elif not is_textual_content(content_type):
            body = summarize_by_type(content_type, None)
        else:
            try:
                body = summarize_by_type(content_type, response.get_data(as_text=True))
            except (RuntimeError, UnicodeDecodeError):
                try:
                    body = summarize_by_type(content_type, response.get_data())
                except RuntimeError:
                    body = "[响应内容不可读取]"

        log_line(f"响应状态: {response.status}")
        log_line(f"响应内容: {body}")
        return response

    # 注册蓝图
    register_blueprints(app)

    # CORS
    CORS(app, resources=r"/*")

    return app


# ==================================================
# 主运行入口
# ==================================================
app = create_app()
