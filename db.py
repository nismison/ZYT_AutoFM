import os
from datetime import datetime

from peewee import *

from utils.logger import log_line

_db = SqliteDatabase(
    'uploads.db',
    pragmas={
        'journal_mode': 'wal',
        'cache_size': -64000,
        'foreign_keys': 1,
        'ignore_check_constraints': 0,
        'synchronous': 'normal',
    },
)


class BaseModel(Model):
    class Meta:
        database = _db


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


class UploadTask(BaseModel):
    """
    后台异步上传 Immich 的任务队列
    由 /upload_to_gallery 接口写入任务
    后台线程 / 后台进程自动消费
    """

    tmp_path = CharField(max_length=500)  # 临时文件完整路径
    etag = CharField(max_length=32)  # 前端传入的校验
    original_filename = CharField(max_length=255)
    suffix = CharField(max_length=10)  # 文件扩展名（.jpg/.png/.mp4）
    status = CharField(max_length=20, default="pending")
    # 状态：pending / processing / done / failed

    retry = IntegerField(default=0)  # 重试次数，未来你要加重试机制可用
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'upload_task'
        indexes = (
            (('status', 'created_at'), False),
        )


class UploadChunkSession(BaseModel):
    """
    用于记录每个分片上传进度
    """

    upload_id = CharField(primary_key=True)
    file_md5 = CharField()
    filename = CharField()
    total_parts = IntegerField()
    uploaded_parts = TextField()  # [
    created_at = DateTimeField(default=datetime.now)
    status = CharField(default="uploading")  # uploading | merged | failed


def init_database_connection():
    """
    初始化当前进程的数据库连接（worker 执行）。
    """
    if _db.is_closed():
        _db.connect(reuse_if_open=True)
        log_line(f"[INFO] [PID {os.getpid()}] DB 连接建立完毕")


def init_wal_mode():
    """
    主进程设置 WAL（只需要一次）
    """
    _db.connect(reuse_if_open=True)
    _db.execute_sql("PRAGMA journal_mode=WAL;")
    log_line("[INFO] SQLite WAL 已启用")


def create_tables_once():
    """
    主进程建表
    """
    init_wal_mode()
    _db.create_tables([UploadRecord, UploadTask], safe=True)
    log_line("[INFO] 数据库表结构初始化完成")
