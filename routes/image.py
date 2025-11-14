import hashlib
import os
import time

from flask import Blueprint, jsonify, request, make_response, send_file
from werkzeug.http import http_date

from config import GALLERY_STORAGE_DIR, GALLERY_CACHE_DIR, WATERMARK_STORAGE_DIR
from utils.logger import log_line

bp = Blueprint("image", __name__)


@bp.route("/api/image/<image_type>/<path:image_id>")
def serve_image(image_type, image_id):
    """
    图片外链（支持 gallery / watermark / gallery_cache / reviews）
    reviews 支持多层目录结构
    """
    try:
        # ------- 1. 处理基础目录 -------
        if image_type == "gallery":
            base = GALLERY_STORAGE_DIR

        elif image_type == "watermark":
            base = WATERMARK_STORAGE_DIR

        elif image_type == "gallery_cache":
            base = GALLERY_CACHE_DIR

        elif image_type == "reviews":
            # 你的目录结构如下：
            # storage/reviews/pending/aaa/bbb/xxx.jpg
            base = os.path.join("storage", "reviews")

            # reviews 的 image_id 是完整相对路径，例如：
            # pending/aaa/bbb/xxx.jpg
            rel_path = image_id.replace("\\", "/")
            path = os.path.join(base, rel_path)

            if not os.path.exists(path):
                return jsonify({"error": "Review 图片不存在"}), 404

            return _serve_file_with_cache(path)

        else:
            return jsonify({"error": "无效的图片类型"}), 400

        # ------- 2. 原有 gallery 逻辑（保持不变） -------
        files = os.listdir(base)
        match = next((f for f in files if f.startswith(image_id)), None)
        if not match:
            return jsonify({"error": "图片不存在"}), 404

        path = os.path.join(base, match)
        if not os.path.exists(path):
            return jsonify({"error": "图片文件不存在"}), 404

        return _serve_file_with_cache(path)

    except Exception as e:
        log_line(f"获取图片失败: {e}")
        return jsonify({"error": str(e)}), 500



def _serve_file_with_cache(path):
    """统一封装图片返回逻辑，减少重复代码"""
    stat = os.stat(path)
    etag = hashlib.md5(f"{stat.st_mtime}-{stat.st_size}".encode()).hexdigest()
    last_modified = http_date(stat.st_mtime)

    # 缓存检查
    if request.headers.get("If-None-Match") == etag:
        return "", 304
    if request.headers.get("If-Modified-Since") == last_modified:
        return "", 304

    resp = make_response(send_file(path, mimetype='image/jpeg', as_attachment=False))
    resp.headers['ETag'] = etag
    resp.headers['Last-Modified'] = last_modified
    resp.headers['Cache-Control'] = 'public, max-age=2592000'
    resp.headers['Expires'] = http_date(time.time() + 2592000)
    return resp
