import hashlib
import os
import time

from flask import Blueprint, jsonify, request, make_response, send_file
from werkzeug.http import http_date

from config import GALLERY_STORAGE_DIR, GALLERY_CACHE_DIR, WATERMARK_STORAGE_DIR
from utils.logger import log_line

bp = Blueprint("image", __name__)


@bp.route("/api/image/<image_type>/<image_id>")
def serve_image(image_type, image_id):
    """图片外链，附带浏览器缓存控制"""
    try:
        if image_type == 'gallery':
            base = GALLERY_STORAGE_DIR
        elif image_type == 'watermark':
            base = WATERMARK_STORAGE_DIR
        elif image_type == 'gallery_cache':
            base = GALLERY_CACHE_DIR
        else:
            return jsonify({"error": "无效的图片类型"}), 400

        files = os.listdir(base)
        match = next((f for f in files if f.startswith(image_id)), None)
        if not match:
            return jsonify({"error": "图片不存在"}), 404

        path = os.path.join(base, match)
        if not os.path.exists(path):
            return jsonify({"error": "图片文件不存在"}), 404

        # ETag + Last-Modified
        stat = os.stat(path)
        etag = hashlib.md5(f"{stat.st_mtime}-{stat.st_size}".encode()).hexdigest()
        last_modified = http_date(stat.st_mtime)

        if request.headers.get("If-None-Match") == etag:
            return "", 304
        if request.headers.get("If-Modified-Since") == last_modified:
            return "", 304

        resp = make_response(send_file(path, mimetype='image/jpeg', as_attachment=False, download_name=match))
        resp.headers['ETag'] = etag
        resp.headers['Last-Modified'] = last_modified
        resp.headers['Cache-Control'] = 'public, max-age=2592000'
        resp.headers['Expires'] = http_date(time.time() + 2592000)
        return resp

    except Exception as e:
        log_line(f"获取图片失败: {e}")
        return jsonify({"error": str(e)}), 500