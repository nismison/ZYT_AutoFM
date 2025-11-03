import logging
import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from math import ceil
from time import sleep

from PIL import Image
from flask import Flask, jsonify, request
from peewee import *
from flask_cors import CORS

from GenerateWaterMark import add_watermark_to_image
from Notification import Notify
from fm_api import FMApi
from oss_client import OSSClient

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


# ==================== 上传线程池 ====================
MAX_UPLOAD_THREADS = 5
upload_executor = ThreadPoolExecutor(
    max_workers=MAX_UPLOAD_THREADS,
    thread_name_prefix='upload_worker'
)

# ==================== 上传目录 ====================
UPLOAD_TEMP_DIR = os.path.join(os.path.dirname(__file__), 'upload_temp')
os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)


# ==================== Flask 应用工厂 ====================
def create_app():
    """创建 Flask 应用（支持多进程 + 多线程）"""
    app = Flask(__name__)
    init_database_connection()

    # 延迟初始化外部依赖（lazy load）
    fm = None
    oss = None

    def get_fm():
        nonlocal fm
        if fm is None:
            logger.info(f"[PID {os.getpid()}] 延迟初始化 FMApi...")
            for i in range(3):  # 初始化重试
                try:
                    fm = FMApi()
                    logger.info(f"[PID {os.getpid()}] FMApi 初始化成功")
                    break
                except Exception as e:
                    logger.error(f"[PID {os.getpid()}] FMApi 初始化失败({i+1}/3): {e}")
                    sleep(2)
            if fm is None:
                raise RuntimeError("FMApi 初始化失败")
        return fm

    def get_oss():
        nonlocal oss
        if oss is None:
            fm_instance = get_fm()
            logger.info(f"[PID {os.getpid()}] 延迟初始化 OSSClient...")
            for i in range(3):
                try:
                    oss_instance = OSSClient(fm_instance.session, fm_instance.token)
                    oss = oss_instance
                    logger.info(f"[PID {os.getpid()}] OSSClient 初始化成功")
                    break
                except Exception as e:
                    logger.error(f"[PID {os.getpid()}] OSSClient 初始化失败({i+1}/3): {e}")
                    sleep(2)
            if oss is None:
                raise RuntimeError("OSSClient 初始化失败")
        return oss

    # ==================== 内部工具 ====================
    def adjust_time_for_display(dt):
        """UTC 转本地时间 (+8小时)"""
        return dt + timedelta(hours=8)

    # ==================== 请求前日志 ====================
    @app.before_request
    def log_request_pid():
        logger.info(f"[PID {os.getpid()}] 处理请求: {request.path}")

    # ==================== 路由定义 ====================
    @app.route('/gallery')
    def serve_vue():
        return app.send_static_file('index.html')

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
                "record": {
                    "id": record.id,
                    "oss_url": record.oss_url,
                    "etag": record.etag,
                    "upload_time": adjust_time_for_display(record.upload_time).strftime("%Y-%m-%d %H:%M:%S")
                }
            })
        else:
            return jsonify({"success": True, "uploaded": False})

    @app.route("/upload_with_watermark", methods=["POST"])
    def upload_with_watermark():
        """上传并添加水印"""
        original_path, result_path = None, None
        try:
            name = request.form.get('name')
            user_number = request.form.get('user_number')
            base_date = request.form.get('base_date')
            base_time = request.form.get('base_time')
            etag = request.form.get('etag')
            file = request.files.get('file')

            if not all([name, user_number, file]):
                return jsonify({"error": "缺少必要参数(name, user_number, file)"}), 400

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                file.save(tmp.name)
                original_path = tmp.name

            result_path = os.path.join(tempfile.gettempdir(), f"wm_{user_number}_{os.getpid()}.jpg")

            add_watermark_to_image(
                original_image_path=original_path,
                name=name,
                user_number=user_number,
                base_date=base_date,
                base_time=base_time,
                output_path=result_path
            )

            oss_url = get_oss().upload(result_path)

            return jsonify({
                "success": True,
                "oss_url": oss_url,
                "etag": etag
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)}), 500

        finally:
            for path in [original_path, result_path]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass

    def background_upload_task(file_path, filename, file_size, device_model, etag, width, height):
        """后台上传任务"""
        try:
            logger.info(f"[后台任务] 开始上传文件: {filename}")
            oss_url = get_oss().upload(file_path)
            logger.info(f"[后台任务] OSS上传成功: {oss_url}")

            try:
                UploadRecord.create(
                    oss_url=oss_url,
                    file_size=file_size,
                    device_model=device_model,
                    original_filename=filename,
                    upload_time=datetime.now(),
                    etag=etag,
                    width=width,
                    height=height
                )
                logger.info(f"[后台任务] 数据库记录保存成功: {filename}")
            except Exception as e:
                logger.error(f"[后台任务] 数据库保存失败: {e}")

            return {"success": True, "oss_url": oss_url, "filename": filename}

        except Exception as e:
            logger.error(f"[后台任务] 上传失败: {e}")
            return {"success": False, "error": str(e)}

        finally:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"[后台任务] 临时文件已清理: {file_path}")
                except Exception as e:
                    logger.error(f"[后台任务] 清理临时文件失败: {e}")

    @app.route("/upload_to_gallery", methods=["POST"])
    def upload_to_gallery():
        """上传到相册（异步后台处理）"""
        try:
            file = request.files.get('file')
            device_model = request.form.get('device_model', '')
            etag = request.form.get('etag', '')

            if not all([file, device_model, etag]):
                return jsonify({"error": "缺少必要参数(file, device_model, etag)"}), 400

            filename = file.filename
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            temp_file_path = os.path.join(UPLOAD_TEMP_DIR, unique_filename)
            file.save(temp_file_path)

            file_size = os.path.getsize(temp_file_path)
            img = Image.open(temp_file_path)
            width, height = img.width, img.height

            upload_executor.submit(
                background_upload_task,
                temp_file_path, filename, file_size, device_model, etag, width, height
            )

            return jsonify({
                "success": True,
                "message": "文件已接收，正在后台上传",
                "filename": filename,
                "size": file_size,
                "etag": etag
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

    @app.route("/upload_policy", methods=["GET"])
    def upload_policy():
        policy = get_oss().get_oss_policy()
        return jsonify({"success": True, "oss_policy": policy})

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
                    "upload_time": adjust_time_for_display(r.upload_time).strftime("%Y-%m-%d %H:%M:%S"),
                    "file_size": r.file_size,
                    "favorite": r.favorite,
                    "etag": r.etag,
                    "width": r.width,
                    "height": r.height
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
                    "upload_time": adjust_time_for_display(r.upload_time).strftime("%Y-%m-%d %H:%M:%S"),
                    "file_size": r.file_size,
                    "favorite": r.favorite,
                    "etag": r.etag,
                    "width": r.width,
                    "height": r.height
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