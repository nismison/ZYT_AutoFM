import os
from datetime import datetime

import pymysql
pymysql.install_as_MySQLdb()  # 告诉 peewee 使用 PyMySQL 作为 MySQLdb

from peewee import *

from utils.logger import log_line

# ---------------------------------------------------------
#  MySQL 数据库配置（把 user / password / host / port 换成你自己的）
# ---------------------------------------------------------
_db = MySQLDatabase(
    'uploads',  # 数据库名
    user='nismison',  # 用户名
    password='lzz22222222',
    host='127.0.0.1',
    port=3306,
    charset='utf8mb4'
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
        # 非唯一索引，和原来保持一致
        indexes = (
            (('etag',), False),
        )


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

    retry = IntegerField(default=0)  # 重试次数
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'upload_task'
        indexes = (
            (('status', 'created_at'), False),
        )


# ---------------------------------------------------------
#  连接 & 初始化函数（名字保持不变，方便你原来的调用）
# ---------------------------------------------------------
def init_database_connection():
    """
    初始化当前进程的数据库连接（worker 执行）。
    """
    if _db.is_closed():
        _db.connect(reuse_if_open=True)
        log_line(f"[INFO] [PID {os.getpid()}] MySQL DB 连接建立完毕")


def init_wal_mode():
    """
    兼容旧接口：原来用于 SQLite WAL。
    现在换成 MySQL，只做一次连接检测和日志输出。
    """
    if _db.is_closed():
        _db.connect(reuse_if_open=True)
    log_line("[INFO] MySQL 数据库已连接（兼容原 init_wal_mode 调用）")


def create_tables_once():
    """
    主进程建表（如果你已经在 MySQL 中手动建好表，这里不会覆盖，只会在不存在时创建）。
    """
    init_database_connection()
    _db.create_tables([UploadRecord, UploadTask], safe=True)
    log_line("[INFO] MySQL 数据库表结构检查/初始化完成")
