import logging
import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from math import ceil

from flask import Flask, jsonify, request
from peewee import *

from GenerateWaterMark import add_watermark_to_image
from Notification import Notify
from fm_api import FMApi
from oss_client import OSSClient

logger = logging.getLogger(__name__)

# ==================== 数据库配置 ====================
db = SqliteDatabase(
    'uploads.db',
    pragmas={
        'journal_mode': 'wal',  # 支持并发读写
        'cache_size': -1024 * 64,
        'foreign_keys': 1,
        'synchronous': 0
    },
    timeout=10
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

    class Meta:
        table_name = 'upload_records'
        indexes = (
            (('etag',), False),
        )


# ==================== 初始化数据库 ====================
def init_database():
    if db.is_closed():
        db.connect(reuse_if_open=True)
    db.create_tables([UploadRecord], safe=True)
    db.execute_sql("PRAGMA journal_mode=WAL;")
    logger.info("数据库初始化完成(WAL模式启用)")


# ==================== 创建持久化的上传目录 ====================
UPLOAD_TEMP_DIR = os.path.join(os.path.dirname(__file__), 'upload_temp')
os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)

# ==================== 创建线程池，设置最大并发数 ====================
MAX_UPLOAD_THREADS = 5  # 最多同时5个上传任务
upload_executor = ThreadPoolExecutor(
    max_workers=MAX_UPLOAD_THREADS,
    thread_name_prefix='upload_worker'
)


# ==================== Flask 应用工厂 ====================
def create_app():
    """创建 Flask 应用（Gunicorn 可用）"""
    app = Flask(__name__)

    # 初始化 FM + OSS 模块
    fm = FMApi()
    oss = OSSClient(fm.session, fm.token)

    # ==================== 内部工具 ====================
    def adjust_time_for_display(dt):
        """UTC 时间转显示时间 (+8 小时)"""
        return dt + timedelta(hours=8)

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

            oss_url = oss.upload(result_path)

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

    def background_upload_task(file_path, filename, file_size, device_model, etag):
        """后台上传任务"""
        try:
            logging.info(f"[后台任务] 开始上传文件: {filename}")

            # 上传到OSS
            oss_url = oss.upload(file_path)
            logging.info(f"[后台任务] OSS上传成功: {oss_url}")

            # 保存数据库记录
            try:
                UploadRecord.create(
                    oss_url=oss_url,
                    file_size=file_size,
                    device_model=device_model,
                    original_filename=filename,
                    upload_time=datetime.now(),
                    etag=etag
                )
                logging.info(f"[后台任务] 数据库记录保存成功: {filename}")
            except Exception as e:
                logging.error(f"[后台任务] 数据库保存失败: {e}")
                import traceback
                traceback.print_exc()

            return {"success": True, "oss_url": oss_url, "filename": filename}

        except Exception as e:
            logging.info(f"[后台任务] 上传失败: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

        finally:
            # 清理临时文件
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logging.info(f"[后台任务] 临时文件已清理: {file_path}")
                except Exception as e:
                    logging.error(f"[后台任务] 清理临时文件失败: {e}")

    @app.route("/upload_to_gallery", methods=["POST"])
    def upload_to_gallery():
        """上传到相册（异步后台处理）"""
        try:
            file = request.files.get('file')
            device_model = request.form.get('device_model', '')
            etag = request.form.get('etag', '')

            if not all([file, device_model, etag]):
                return jsonify({"error": "缺少必要参数(file, device_model, etag)"}), 400

            # 获取文件信息
            filename = file.filename

            # 生成唯一的文件名，避免冲突
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            temp_file_path = os.path.join(UPLOAD_TEMP_DIR, unique_filename)

            # 保存文件到持久化临时目录
            file.save(temp_file_path)

            # 获取文件大小
            file_size = os.path.getsize(temp_file_path)

            # 提交任务到线程池（如果队列满了会自动等待）
            future = upload_executor.submit(
                background_upload_task,
                temp_file_path, filename, file_size, device_model, etag
            )

            # 立即返回成功响应
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
        """手动触发推送通知"""
        data = request.get_json(silent=True) or {}
        content = data.get("content")
        if not content:
            return jsonify({"error": "缺少content"}), 400
        notify.send(content)
        return jsonify({"success": True})

    @app.route("/upload_policy", methods=["GET"])
    def upload_policy():
        """
        获取上传策略
        :return: OSS上传策略
        """
        policy = oss.get_oss_policy()
        return jsonify({
            "success": True,
            "oss_policy": policy
        })

    @app.route("/api/favorite/<int:record_id>", methods=["POST"])
    def toggle_favorite(record_id):
        """
        切换记录的收藏状态
        :param record_id: 记录ID
        :return: 更新后的收藏状态
        """
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
        """
        获取收藏的图片记录(支持分页)
        参数:
            page: 页码,默认1
            size: 每页数量,默认20
        返回:
            {
                "success": true,
                "data": {
                    "records": [...],
                    "page": 1,
                    "total_pages": 3,
                    "total": 56
                }
            }
        """
        page = int(request.args.get("page", 1))
        size = int(request.args.get("size", 20))

        # 查询收藏的记录
        query = UploadRecord.select().where(UploadRecord.favorite == True).order_by(UploadRecord.upload_time.desc())

        total = query.count()
        total_pages = max(ceil(total / size), 1)
        records = query.paginate(page, size)

        return jsonify({
            "success": True,
            "data": {
                "records": [
                    {
                        "id": r.id,
                        "oss_url": r.oss_url,
                        "filename": r.original_filename,
                        "device_model": r.device_model,
                        "upload_time": adjust_time_for_display(r.upload_time).strftime("%Y-%m-%d %H:%M:%S"),
                        "file_size": r.file_size,
                        "favorite": r.favorite,
                        "etag": r.etag  # 返回etag
                    } for r in records
                ],
                "page": page,
                "total_pages": total_pages,
                "total": total
            }
        })

    @app.route("/api/gallery", methods=["GET"])
    def api_gallery():
        """分页获取图片记录"""
        page = int(request.args.get("page", 1))
        size = int(request.args.get("size", 20))
        device = request.args.get("device", "").strip()

        query = UploadRecord.select().order_by(UploadRecord.upload_time.desc())
        if device:
            query = query.where(UploadRecord.device_model == device)

        total = query.count()
        total_pages = max(ceil(total / size), 1)
        records = query.paginate(page, size)

        devices = (
            UploadRecord.select(UploadRecord.device_model)
                .distinct()
                .order_by(UploadRecord.device_model)
                .tuples()
        )
        devices = [d[0] for d in devices if d[0]]

        return jsonify({
            "success": True,
            "data": {
                "records": [
                    {
                        "id": r.id,
                        "oss_url": r.oss_url,
                        "filename": r.original_filename,
                        "device_model": r.device_model,
                        "upload_time": adjust_time_for_display(r.upload_time).strftime("%Y-%m-%d %H:%M:%S"),
                        "file_size": r.file_size,
                        "favorite": r.favorite,
                        "etag": r.etag
                    } for r in records
                ],
                "page": page,
                "total_pages": total_pages,
                "total": total,
                "devices": devices
            }
        })

    return app


# ==================== Gunicorn 兼容 ====================
# Gunicorn 运行时会直接导入 `app` 对象
init_database()
app = create_app()

# ==================== 开发模式启动 ====================
if __name__ == '__main__':
    app.run(host="192.168.1.9", port=5001, debug=True)
