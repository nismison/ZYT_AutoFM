import os
from datetime import datetime
from peewee import *

# SQLite 数据库，启用 WAL，适合多进程读多写少
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


def init_database_connection():
    """为当前进程建立数据库连接，并开启 WAL"""
    if _db.is_closed():
        _db.connect(reuse_if_open=True)
        _db.execute_sql("PRAGMA journal_mode=WAL;")
        log_line(f"[PID {os.getpid()}] 数据库连接已建立 (WAL 启用)")


def ensure_tables():
    """确保表结构存在"""
    try:
        init_database_connection()
        _db.create_tables([UploadRecord], safe=True)
        log_line("[主进程] 数据库表结构初始化完成")
    except Exception as e:
        log_line(f"[Gunicorn] 数据库表结构初始化失败: {e}")