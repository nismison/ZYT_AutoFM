import hashlib
import json
import os
import random
import string
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from math import ceil

import requests
from PIL import Image
from flask import Flask, jsonify, request, send_file, make_response, Response
from flask_cors import CORS
from peewee import *
from werkzeug.http import http_date
from werkzeug.utils import secure_filename

from config import GALLERY_STORAGE_DIR, GALLERY_CACHE_DIR, WATERMARK_STORAGE_DIR, logger, BASE_URL, TARGET_BASE, \
    IMMICH_API_KEY, IMMICH_URL
from generate_water_mark import add_watermark_to_image
from notification import Notify

# ==================== 数据库配置 ====================
from ql_api import QLApi

db = SqliteDatabase(
    'uploads.db',
    pragmas={
        'journal_mode': 'wal',
        'cache_size': -64000,
        'foreign_keys': 1,
        'ignore_check_constraints': 0,
        'synchronous': 'normal'
    }
)

notify = Notify()

# ==================== 本地存储配置 ====================
os.makedirs(GALLERY_STORAGE_DIR, exist_ok=True)
os.makedirs(GALLERY_CACHE_DIR, exist_ok=True)
os.makedirs(WATERMARK_STORAGE_DIR, exist_ok=True)


# ==================== ORM 模型定义 ====================
class BaseModel(Model):
    class Meta:
        database = db


class UploadRecord(BaseModel):
    """上传记录表"""
    oss_url = CharField(max_length=500)
    file_size = IntegerField()
    device_model = CharField(max_length=100, null=True)
    upload_time = DateTimeField(default=datetime.now)
    original_filename = CharField(max_length=255, null=True)
    favorite = BooleanField(default=False)
    etag = CharField(max_length=32, null=True)
    width = IntegerField()
    height = IntegerField()
    thumb = CharField(max_length=500, null=True)

    class Meta:
        table_name = 'upload_records'
        indexes = ((('etag',), False),)


# ==================== 数据库初始化函数 ====================
def init_database_connection():
    """为当前进程建立数据库连接"""
    if db.is_closed():
        db.connect(reuse_if_open=True)
        db.execute_sql("PRAGMA journal_mode=WAL;")
        logger.info(f"[PID {os.getpid()}] 数据库连接已建立 (WAL 模式启用)")


def ensure_tables():
    """只在主进程中执行一次表结构检查"""
    init_database_connection()
    db.create_tables([UploadRecord], safe=True)
    logger.info("[主进程] 数据库表结构检查完成")


# ==================== 本地存储工具函数 ====================
def generate_random_suffix(length=8):
    """生成随机字符串后缀"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def get_image_url(image_id, image_type='gallery'):
    """
    生成图片外链URL
    image_type: 'gallery' 或 'watermark' 或 'gallery_cache'
    """
    return f"{BASE_URL}/api/image/{image_type}/{image_id}"


def upload_to_immich_file(file_path):
    """根据官方示例上传文件到 Immich"""
    stats = os.stat(file_path)

    headers = {
        'Accept': 'application/json',
        'x-api-key': IMMICH_API_KEY
    }

    file_created = datetime.fromtimestamp(stats.st_mtime)

    data = {
        'deviceAssetId': f'{os.path.basename(file_path)}-{stats.st_mtime}',
        'deviceId': 'python',
        'fileCreatedAt': file_created,
        'fileModifiedAt': file_created,
        'isFavorite': 'false',
    }

    files = {
        'assetData': open(file_path, 'rb')
    }

    response = requests.post(
        f'{IMMICH_URL}/assets', headers=headers, data=data, files=files)

    files['assetData'].close()

    try:
        return response.json()
    except Exception:
        return jsonify({"status": "fail"})


def merge_images_grid(image_paths, target_width=1500, padding=4, bg_color=(255, 255, 255)):
    """
    自适应拼贴图布局（不留白，不强制相同尺寸）
    - 自动调整每行高度，保持整体宽度一致
    - 各行图片等比例缩放，填满整行
    - 整体效果类似瀑布流/拼贴墙
    """
    from PIL import Image
    images = [Image.open(p).convert("RGB") for p in image_paths]
    n = len(images)
    if n == 0:
        raise ValueError("No images provided")

    # 计算行数（尽量接近正方形视觉）
    import math
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    # 按行分组
    groups = []
    idx = 0
    for _ in range(rows):
        remain = n - idx
        count = min(cols, remain)
        groups.append(images[idx:idx + count])
        idx += count

    y_offset = 0
    row_images = []
    total_height = 0

    # 每行自动缩放填满 target_width
    for row_imgs in groups:
        # 行内原始宽高比例总和
        ratios = [img.width / img.height for img in row_imgs]
        total_ratio = sum(ratios)
        # 行高按目标宽计算
        row_height = int(target_width / total_ratio)
        scaled_row = []
        for img, ratio in zip(row_imgs, ratios):
            new_w = int(row_height * ratio)
            scaled_row.append(img.resize((new_w, row_height)))
        row_images.append(scaled_row)
        total_height += row_height + padding

    # 创建最终画布
    merged = Image.new("RGB", (target_width, total_height - padding), bg_color)

    y = 0
    for row in row_images:
        x = 0
        for img in row:
            merged.paste(img, (x, y))
            x += img.width + padding
            img.close()
        y += row[0].height + padding

    return merged


# ==================== Flask 应用工厂 ====================
def create_app():
    """创建 Flask 应用"""
    app = Flask(__name__)
    init_database_connection()

    # ==================== 请求前日志 ====================
    @app.before_request
    def log_request_pid():
        logger.info(f"[PID {os.getpid()}] 处理请求: {request.path}")

    # ==================== 路由定义 ====================
    @app.route('/redirect', defaults={'subpath': ''}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    @app.route('/redirect/<path:subpath>', methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    def proxy(subpath):
        # 获取原始请求路径，去掉 /redirect 前缀
        original_path = request.path[len('/redirect'):]  # 保留前导斜杠
        # 去掉开头多余的 /，确保拼接 TARGET_BASE 不会出现双斜杠
        original_path = original_path.lstrip('/')

        target_url = f"{TARGET_BASE}/{original_path}"

        # 获取请求的 headers（去掉 host）
        headers = {k: v for k, v in request.headers if k.lower() != 'host'}

        # 转发请求到目标
        try:
            resp = requests.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.args,  # 查询参数
                data=request.get_data(),  # 原始 body 数据
                cookies=request.cookies,
                allow_redirects=False,  # 不在服务器端自动跟随重定向
                timeout=30,
                proxies={}  # 禁用代理
            )
        except requests.RequestException as e:
            return Response(f"Upstream request failed: {e}", status=502)

        # 构造返回 Response，原样转发响应
        excluded_headers = [
            'content-encoding', 'transfer-encoding', 'connection'
        ]
        headers = {
            name: value
            for name, value in resp.headers.items()
            if name.lower() not in excluded_headers
        }

        if original_path == "heimdall/api/oauth/access_token" and resp.status_code == 200:
            access_token = (resp.json().get('result') or {}).get('access_token')
            ql = QLApi()
            success = ql.update_env("ZYT_TOKEN", access_token)
            print("更新成功" if success else "更新失败")
            if success:
                Notify().send(f"Token更新成功: ...{access_token[-10:]}")
            else:
                Notify().send(f"Token更新失败")

        return Response(resp.content, resp.status_code, headers)

    @app.route("/api/image/<image_type>/<image_id>")
    def serve_image(image_type, image_id):
        """
        图片外链接口 - 带浏览器缓存支持
        """
        try:
            # 选择目录
            if image_type == 'gallery':
                storage_dir = GALLERY_STORAGE_DIR
            elif image_type == 'watermark':
                storage_dir = WATERMARK_STORAGE_DIR
            elif image_type == 'gallery_cache':
                storage_dir = GALLERY_CACHE_DIR
            else:
                return jsonify({"error": "无效的图片类型"}), 400

            # 查找对应的文件
            files = os.listdir(storage_dir)
            matching_file = next((f for f in files if f.startswith(image_id)), None)
            if not matching_file:
                return jsonify({"error": "图片不存在"}), 404

            image_path = os.path.join(storage_dir, matching_file)
            if not os.path.exists(image_path):
                return jsonify({"error": "图片文件不存在"}), 404

            # ==== 🔒 缓存处理部分 ====

            # 1. 生成 ETag（用文件修改时间和大小）
            stat = os.stat(image_path)
            etag = hashlib.md5(f"{stat.st_mtime}-{stat.st_size}".encode()).hexdigest()

            # 2. 获取修改时间
            last_modified = http_date(stat.st_mtime)

            # 3. 判断客户端缓存是否有效
            if request.headers.get("If-None-Match") == etag:
                return "", 304
            if request.headers.get("If-Modified-Since") == last_modified:
                return "", 304

            # ==== 🔄 返回文件并附带缓存头 ====
            response = make_response(send_file(
                image_path,
                mimetype='image/jpeg',
                as_attachment=False,
                download_name=matching_file
            ))

            # 设置 HTTP 缓存头
            response.headers["ETag"] = etag
            response.headers["Last-Modified"] = last_modified
            response.headers["Cache-Control"] = "public, max-age=2592000"  # 缓存30天
            response.headers["Expires"] = http_date(time.time() + 2592000)

            return response

        except Exception as e:
            logger.error(f"获取图片失败: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/check_uploaded", methods=["GET"])
    def check_uploaded():
        etag = request.args.get("etag", "").strip()
        if not etag:
            return jsonify({"success": False, "error": "缺少etag"}), 400

        record = (UploadRecord
                  .select()
                  .where(UploadRecord.etag == etag)
                  .order_by(UploadRecord.upload_time.desc())
                  .first())

        if record:
            return jsonify({
                "success": True,
                "uploaded": True,
            })
        else:
            return jsonify({"success": True, "uploaded": False})

    @app.route("/upload_with_watermark", methods=["POST"])
    def upload_with_watermark():
        """上传并添加水印（支持单文件/多文件，可选合并为一张图）"""
        try:
            name = request.form.get('name')
            user_number = request.form.get('user_number')
            base_date = request.form.get('base_date')
            base_time = request.form.get('base_time')
            merge = request.form.get('merge') == "true"

            # 获取所有文件（兼容 file、file0、file1...）
            files = []
            for key in request.files.keys():
                files += request.files.getlist(key)
            if not files and 'file' in request.files:
                files = [request.files['file']]

            if not all([name, user_number]) or not files:
                return jsonify({"error": "缺少必要参数(name, user_number, file)"}), 400

            # 初始化时间
            if base_date and base_time:
                current_time = datetime.strptime(f"{base_date} {base_time}", "%Y-%m-%d %H:%M")
            else:
                current_time = datetime.now()

            result_paths = []
            temp_paths = []

            # 生成单张水印图
            for file in files:
                fd, original_path = tempfile.mkstemp(suffix=".jpg")
                os.close(fd)
                file.save(original_path)
                temp_paths.append(original_path)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                random_suffix = generate_random_suffix()
                image_id = f"{user_number}_{timestamp}_{random_suffix}"
                result_filename = f"{image_id}.jpg"
                result_path = os.path.join(WATERMARK_STORAGE_DIR, result_filename)

                # 每张图片时间 +1~2 分钟
                current_time += timedelta(minutes=random.randint(1, 2))
                time_str = current_time.strftime("%H:%M")

                add_watermark_to_image(
                    original_image_path=original_path,
                    name=name,
                    user_number=user_number,
                    base_date=base_date or datetime.now().strftime("%Y-%m-%d"),
                    base_time=time_str,
                    output_path=result_path
                )

                result_paths.append((image_id, result_path))

            # 合并模式
            if merge and len(result_paths) > 1:
                merged_image = merge_images_grid([p[1] for p in result_paths])
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                random_suffix = generate_random_suffix()
                merged_id = f"{user_number}_{timestamp}_{random_suffix}_merged"
                merged_filename = f"{merged_id}.jpg"
                merged_path = os.path.join(WATERMARK_STORAGE_DIR, merged_filename)
                merged_image.save(merged_path, quality=90, optimize=True)
                merged_image.close()

                oss_urls = [get_image_url(merged_id, 'watermark')]

            # 不合并 → 返回所有直链
            else:
                oss_urls = [get_image_url(iid, 'watermark') for iid, _ in result_paths]

            # 清理临时文件
            for p in temp_paths:
                try:
                    os.remove(p)
                except Exception:
                    pass

            logger.info(f"生成水印图片 {len(oss_urls)} 张（merge={merge}）")

            return jsonify({
                "success": True,
                "oss_urls": oss_urls,
                "count": len(oss_urls)
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/upload_to_gallery", methods=["POST"])
    def upload_to_gallery():
        """上传到相册 - 保存到相册目录（持久保存）"""
        try:
            file = request.files.get('file')
            etag = request.form.get('etag', '')

            if not all([file, etag]):
                return jsonify({"error": "缺少必要参数(file, etag)"}), 400

            # 创建带扩展名的临时文件
            suffix = os.path.splitext(file.filename)[1]  # 例如 ".jpg" ".png" ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name

            result = upload_to_immich_file(tmp_path)
            os.remove(tmp_path)

            # 保存数据库记录
            UploadRecord.create(
                oss_url='oss_url',
                file_size=100,
                upload_time=datetime.now(),
                etag=etag,
                width=500,
                height=500,
            )

            if result.get("error"):
                return jsonify({"success": False, "error": result.get("message")}), 500
            else:
                print(result)
                return jsonify({
                    "success": True,
                    "message": "文件已成功保存",
                }), 200

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/send_notify", methods=["POST"])
    def send_notify():
        data = request.get_json(silent=True) or {}
        content = data.get("content")
        if not content:
            return jsonify({"error": "缺少content"}), 400
        notify.send(content)
        return jsonify({"success": True})

    @app.route("/api/favorite/<int:record_id>", methods=["POST"])
    def toggle_favorite(record_id):
        try:
            record = UploadRecord.get_by_id(record_id)
            record.favorite = not record.favorite
            record.save()
            return jsonify({
                "success": True,
                "favorite": record.favorite,
                "message": f"已{'收藏' if record.favorite else '取消收藏'}"
            })
        except UploadRecord.DoesNotExist:
            return jsonify({"success": False, "error": "记录不存在"}), 404
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/favorites", methods=["GET"])
    def get_favorites():
        page = int(request.args.get("page", 1))
        size = int(request.args.get("size", 20))
        query = UploadRecord.select().where(UploadRecord.favorite == True).order_by(UploadRecord.upload_time.desc())
        total = query.count()
        total_pages = max(ceil(total / size), 1)
        records = query.paginate(page, size)
        devices = [d[0] for d in UploadRecord.select(UploadRecord.device_model).distinct().tuples() if d[0]]

        return jsonify({
            "success": True,
            "data": {
                "records": [{
                    "id": r.id,
                    "oss_url": r.oss_url,
                    "filename": r.original_filename,
                    "device_model": r.device_model,
                    "upload_time": r.upload_time,
                    "file_size": r.file_size,
                    "favorite": r.favorite,
                    "etag": r.etag,
                    "width": r.width,
                    "height": r.height,
                    "thumb": r.thumb
                } for r in records],
                "page": page,
                "total_pages": total_pages,
                "total": total,
                "devices": devices
            }
        })

    @app.route("/api/gallery", methods=["GET"])
    def api_gallery():
        page = int(request.args.get("page", 1))
        size = int(request.args.get("size", 20))
        device = request.args.get("device", "").strip()

        query = UploadRecord.select().order_by(UploadRecord.upload_time.desc())
        if device:
            query = query.where(UploadRecord.device_model == device)

        total = query.count()
        total_pages = max(ceil(total / size), 1)
        records = query.paginate(page, size)
        devices = [d[0] for d in UploadRecord.select(UploadRecord.device_model).distinct().tuples() if d[0]]

        return jsonify({
            "success": True,
            "data": {
                "records": [{
                    "id": r.id,
                    "oss_url": r.oss_url,
                    "filename": r.original_filename,
                    "device_model": r.device_model,
                    "upload_time": r.upload_time,
                    "file_size": r.file_size,
                    "favorite": r.favorite,
                    "etag": r.etag,
                    "width": r.width,
                    "height": r.height,
                    "thumb": r.thumb
                } for r in records],
                "page": page,
                "total_pages": total_pages,
                "total": total,
                "devices": devices
            }
        })

    return app


# ==================== 主程序入口 ====================
if os.getpid() == os.getppid():
    ensure_tables()

app = create_app()
CORS(app, resources=r'/*')

if __name__ == '__main__':
    app.run(host="192.168.1.9", port=5001, debug=True)
