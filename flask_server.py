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
    if not content_type:
        return truncate(data)
    ct = content_type.lower()
    if "image" in ct:
        return "[图片]"
    if "video" in ct:
        return "[视频]"
    if "audio" in ct:
        return "[音频]"
    if "multipart/form-data" in ct or "octet-stream" in ct:
        return "[文件]"
    return truncate(data)


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
            body = summarize_by_type(content_type, request.get_data(as_text=True))

        log_line("=" * 50)
        log_line("请求路径:", request.path)
        log_line("请求数据:", body)

    @app.after_request
    def log_response(response):
        content_type = response.content_type or ""
        if "text/event-stream" in content_type:
            body = "[SSE流]"
        else:
            body = summarize_by_type(content_type, response.get_data(as_text=True))
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
