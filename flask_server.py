from datetime import datetime
from typing import Optional
from urllib.parse import parse_qs

from flask import Flask, request, jsonify
from flask_cors import CORS

from config import db, TZ
from db import init_database_connection, create_tables_once, close_database_connection, UserInfo
from order_handler import init_template_pic_dirs
from routes import register_blueprints
from utils.logger import log_line


# ==================================================
# 工具函数
# ==================================================
def now() -> str:
    return datetime.now(TZ).strftime("[%Y-%m-%d %H:%M:%S]")


def detect_file_type(filename: str) -> str:
    """
    根据文件名后缀判断文件类型（用于 multipart/form-data）
    """
    if not filename:
        return "[文件]"

    ext = filename.lower().rsplit(".", 1)[-1]

    if ext in {"jpg", "jpeg", "png", "gif", "bmp", "webp"}:
        return "[图片]"
    if ext in {"mp4", "mov", "avi", "mkv", "wmv", "flv"}:
        return "[视频]"
    if ext in {"mp3", "wav", "aac", "flac", "m4a", "ogg"}:
        return "[音频]"

    return f"[文件:{ext}]"


def summarize_by_type(content_type, data):
    """
    根据 Content-Type + 内容 生成概要
    """
    text = data or ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")

    if not content_type:
        return text

    ct = content_type.lower()

    if "image" in ct:
        return "[图片]"
    if "video" in ct:
        return "[视频]"
    if "audio" in ct:
        return "[音频]"
    if "multipart/form-data" in ct or "octet-stream" in ct:
        return "[文件]"

    return text


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


def safe_query_dict():
    """安全解析 query，避免过长内容撑爆日志"""
    raw = request.query_string.decode("utf-8", errors="replace")
    if not raw:
        return {}

    # parse_qs 输出 list，转成更可读的结构
    parsed = parse_qs(raw, keep_blank_values=True)

    # 裁剪超长参数，避免打印 token / 大段内容
    safe = {}
    for k, v in parsed.items():
        val = v[0] if v else ""
        if len(val) > 200:
            val = val[:200] + "...(省略)"
        safe[k] = val

    return safe


def init_all_users_template_dirs() -> None:
    for (user_number,) in (
            UserInfo.select(UserInfo.user_number).tuples().iterator()
    ):
        try:
            init_template_pic_dirs(user_number)
        except Exception:
            pass


# ==================================================
# Flask 应用
# ==================================================
def create_app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def log_request():
        """连接数据库"""
        if db.is_closed():
            init_database_connection()

        """请求前日志记录"""
        if should_skip_logging(request.path):
            return

        query_dict = safe_query_dict()
        content_type = request.content_type or ""

        if "multipart/form-data" in content_type:
            form_fields = {k: v for k, v in request.form.items()}
            file_fields = {key: detect_file_type(file.filename) for key, file in request.files.items()}
            body = {"form": form_fields, "files": file_fields}
        else:
            if is_textual_content(content_type):
                try:
                    data = request.get_data(as_text=True)
                except UnicodeDecodeError:
                    data = request.get_data()
            else:
                data = None
            body = summarize_by_type(content_type, data)

        log_text = (
            f"请求日志\n"
            f"路径: {request.path}\n"
            f"查询参数: {query_dict}\n"
            f"请求体: {body}"
        )
        log_line(log_text)

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
            filename = (
                response.headers.get("Content-Disposition", "")
                .replace("attachment;", "")
                .replace("filename=", "")
                .strip('" ')
            )
            if filename:
                body = detect_file_type(filename)
            else:
                body = summarize_by_type(content_type, None)
        else:
            try:
                data = response.get_data(as_text=True)
                body = summarize_by_type(content_type, data)
            except (RuntimeError, UnicodeDecodeError):
                try:
                    body = summarize_by_type(content_type, response.get_data())
                except RuntimeError:
                    body = "[响应内容不可读取]"

        log_text = (
            f"响应日志\n"
            f"路径: {request.path}\n"
            f"状态: {response.status}\n"
            f"响应体: {body}"
        )
        log_line(log_text)

        return response

    @app.teardown_request
    def _db_close(_):
        close_database_connection()

    @app.route("/api/test", methods=["GET"])
    def test():
        return jsonify({
            "success": True
        })

    # 注册蓝图
    register_blueprints(app)

    # CORS
    CORS(app, resources=r"/*")

    # 初始化所有用户的模板目录
    init_all_users_template_dirs()

    return app


# ==================================================
# 主运行入口
# ==================================================
app = create_app()

if __name__ == '__main__':
    create_tables_once()
    app.run(host="192.168.1.9", port=5001, debug=True)
