from datetime import datetime

from flask import Flask, request
from flask_cors import CORS

from config import IS_DEV
from db import init_database_connection
from routes import register_blueprints
from utils.logger import log_line


def now():
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")


def truncate(text, limit=500):
    if not text:
        return ""
    return text[:limit] + ("...（已截断）" if len(text) > limit else "")


def summarize_by_type(content_type, data):
    """返回内容简要说明"""
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


def is_textual_content(content_type: str | None) -> bool:
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


def create_app() -> Flask:
    app = Flask(__name__)

    # DB 连接
    init_database_connection()

    @app.before_request
    def log_request():
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
                    data = request.get_data()  # 回退到字节数据，交由 summarize_by_type 处理
            body = summarize_by_type(content_type, data)

        log_line("=" * 50)
        log_line("请求路径:", request.path)
        log_line("请求数据:", body)

    @app.after_request
    def log_response(response):
        content_type = response.content_type or ""
        if "text/event-stream" in content_type:
            body = "[SSE流]"
        elif getattr(response, "direct_passthrough", False):
            # direct_passthrough 模式下无法读取数据，否则会触发 RuntimeError
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
        log_line("响应状态:", response.status)
        log_line("响应内容:", body)
        return response
    # 蓝图
    register_blueprints(app)

    # CORS
    CORS(app, resources=r'/*')
    return app


app = create_app()

if IS_DEV:
    app.run(host="0.0.0.0", port=5001, debug=True)
