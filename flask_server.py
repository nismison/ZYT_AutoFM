import logging
import os
import random
import string
import tempfile
import uuid
from datetime import datetime
from math import ceil

from PIL import Image
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from peewee import *

from GenerateWaterMark import add_watermark_to_image
from Notification import Notify

logger = logging.getLogger(__name__)

# ==================== 数据库配置 ====================
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
BASE_URL = "https://api.zytsy.icu"

# 相册图片存储目录（持久保存）
GALLERY_STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'gallery')
os.makedirs(GALLERY_STORAGE_DIR, exist_ok=True)

# 缓存图片存储目录（持久保存）
GALLERY_CACHE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'gallery_cache')
os.makedirs(GALLERY_CACHE_DIR, exist_ok=True)

# 水印图片存储目录（定时清理）
WATERMARK_STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'watermark')
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


# ==================== Flask 应用工厂 ====================
def create_app():
    """创建 Flask 应用"""
    flask_app = Flask(__name__)
    init_database_connection()

    # ==================== 请求前日志 ====================
    @flask_app.before_request
    def log_request_pid():
        logger.info(f"[PID {os.getpid()}] 处理请求: {request.path}")

    # ==================== 路由定义 ====================
    @flask_app.route('/gallery')
    def serve_vue():
        return flask_app.send_static_file('index.html')

    @flask_app.route("/api/image/<image_type>/<image_id>")
    def serve_image(image_type, image_id):
        """
        图片外链接口 - 根据image_type和image_id返回图片文件
        image_type: 'gallery' 或 'watermark'
        """
        try:
            # 根据类型选择存储目录
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
            matching_file = None

            for filename in files:
                if filename.startswith(image_id):
                    matching_file = filename
                    break

            if not matching_file:
                return jsonify({"error": "图片不存在"}), 404

            image_path = os.path.join(storage_dir, matching_file)

            if not os.path.exists(image_path):
                return jsonify({"error": "图片文件不存在"}), 404

            # 返回图片文件
            return send_file(
                image_path,
                mimetype='image/jpeg',
                as_attachment=False,
                download_name=matching_file
            )

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

    @flask_app.route("/upload_with_watermark", methods=["POST"])
    def upload_with_watermark():
        """上传并添加水印 - 保存到水印目录"""
        original_path = None
        try:
            name = request.form.get('name')
            user_number = request.form.get('user_number')
            base_date = request.form.get('base_date')
            base_time = request.form.get('base_time')
            file = request.files.get('file')

            if not all([name, user_number, file]):
                return jsonify({"error": "缺少必要参数(name, user_number, file)"}), 400

            # 保存原始文件到临时目录
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                file.save(tmp.name)
                original_path = tmp.name

            # 生成唯一的文件名（添加随机后缀避免重复）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_suffix = generate_random_suffix()
            image_id = f"{user_number}_{timestamp}_{random_suffix}"
            result_filename = f"{image_id}.jpg"
            result_path = os.path.join(WATERMARK_STORAGE_DIR, result_filename)

            # 添加水印，直接输出到水印存储目录
            add_watermark_to_image(
                original_image_path=original_path,
                name=name,
                user_number=user_number,
                base_date=base_date,
                base_time=base_time,
                output_path=result_path
            )

            # 生成外链URL
            oss_url = get_image_url(image_id, 'watermark')

            logger.info(f"水印图片已生成: {result_path} -> {oss_url}")

            return jsonify({
                "success": True,
                "oss_url": oss_url,
                "oss_policy": {}
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)}), 500

        finally:
            # 只清理原始临时文件
            if original_path and os.path.exists(original_path):
                try:
                    os.remove(original_path)
                except Exception:
                    pass

    @flask_app.route("/upload_to_gallery", methods=["POST"])
    def upload_to_gallery():
        """上传到相册 - 保存到相册目录（持久保存）"""
        try:
            file = request.files.get('file')
            device_model = request.form.get('device_model', '')
            etag = request.form.get('etag', '')

            if not all([file, device_model, etag]):
                return jsonify({"error": "缺少必要参数(file, device_model, etag)"}), 400

            filename = file.filename

            # 生成唯一的image_id和文件名
            image_id = uuid.uuid4().hex
            ext = os.path.splitext(filename)[1] or '.jpg'
            local_filename = f"{image_id}{ext}"
            save_path = os.path.join(GALLERY_STORAGE_DIR, local_filename)
            thumb_path = os.path.join(GALLERY_CACHE_DIR, f"{image_id}_thumb{ext}")

            # 直接保存到相册存储目录
            file.save(save_path)

            # 获取文件信息
            file_size = os.path.getsize(save_path)
            img = Image.open(save_path)
            width, height = img.width, img.height
            # 保存预览图
            img.save(thumb_path, quality=50, optimize=True)
            img.close()

            # 生成图片外链URL
            oss_url = get_image_url(image_id, 'gallery')
            thumb_url = get_image_url(image_id, 'gallery_cache')

            # 保存数据库记录
            UploadRecord.create(
                oss_url=oss_url,
                file_size=file_size,
                device_model=device_model,
                original_filename=filename,
                upload_time=datetime.now(),
                etag=etag,
                width=width,
                height=height,
                thumb=thumb_url
            )

            logger.info(f"相册图片已保存: {filename} -> {oss_url}")

            return jsonify({
                "success": True,
                "message": "文件已成功保存",
                "oss_url": oss_url,
                "filename": filename,
                "size": file_size,
                "etag": etag
            }), 200

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)}), 500

    @flask_app.route("/send_notify", methods=["POST"])
    def send_notify():
        data = request.get_json(silent=True) or {}
        content = data.get("content")
        if not content:
            return jsonify({"error": "缺少content"}), 400
        notify.send(content)
        return jsonify({"success": True})

    @flask_app.route("/api/favorite/<int:record_id>", methods=["POST"])
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

    @flask_app.route("/api/favorites", methods=["GET"])
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

    @flask_app.route("/api/gallery", methods=["GET"])
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

    return flask_app


# ==================== 主程序入口 ====================
if os.getpid() == os.getppid():
    ensure_tables()

app = create_app()
CORS(app, resources=r'/*')

if __name__ == '__main__':
    app.run(host="192.168.1.9", port=5001, debug=True)
