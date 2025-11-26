import os
import datetime

import pymysql
from peewee import (
    Model,
    AutoField,
    CharField,
    BigIntegerField,
    IntegerField,
    DateTimeField,
    ForeignKeyField,
    TextField,
    BooleanField,
)
from config import db, FILE_STATUS_INIT
from utils.logger import log_line

# 告诉 peewee 使用 PyMySQL 作为 MySQLdb
pymysql.install_as_MySQLdb()


# =========================
# 统一的 BaseModel
# =========================

class BaseModel(Model):
    """
    统一的基础模型：
    - 仅指定 database，不额外增加字段
    - 这样可以兼容你原有的 UploadRecord/UploadTask/UserInfo 表结构
    - File/UploadSession/UploadPart 之前多出来的 created_at/updated_at 列，即使已在数据库中存在，
      现在不再在模型中声明，也不会影响 Peewee 使用（多余列不会被查询）
    """

    class Meta:
        database = db


# =========================
# 分片上传相关模型
# =========================

class File(BaseModel):
    id = AutoField()
    fingerprint = CharField(max_length=128, unique=True)
    file_name = CharField(max_length=255)
    file_size = BigIntegerField()
    cos_key = CharField(max_length=512)
    url = CharField(max_length=512, null=True)
    status = CharField(max_length=32, default=FILE_STATUS_INIT)

    class Meta:
        table_name = "file"


class UploadSession(BaseModel):
    id = AutoField()
    file = ForeignKeyField(File, backref="sessions", on_delete="CASCADE")
    upload_id = CharField(max_length=255, null=True)
    chunk_size = IntegerField()
    total_chunks = IntegerField()
    uploaded_chunks = IntegerField(default=0)
    status = CharField(max_length=32)

    class Meta:
        table_name = "upload_session"
        # 不额外声明 indexes，避免和外键自动索引冲突


class UploadPart(BaseModel):
    id = AutoField()
    file = ForeignKeyField(File, backref="parts", on_delete="CASCADE")
    part_number = IntegerField()
    etag = CharField(max_length=255)
    status = CharField(max_length=32, default="DONE")
    extra = TextField(null=True)

    class Meta:
        table_name = "upload_part"
        indexes = (
            # file + part_number 组合唯一
            (("file", "part_number"), True),
        )


# =========================
# 你原有的上传记录 / 任务队列 / 用户表
# =========================

class UploadRecord(BaseModel):
    """上传记录表"""
    oss_url = CharField(max_length=500)
    file_size = IntegerField()
    device_model = CharField(max_length=100, null=True)
    upload_time = DateTimeField(default=datetime.datetime.now)
    original_filename = CharField(max_length=255, null=True)
    favorite = BooleanField(default=False)
    etag = CharField(max_length=32, null=True)
    fingerprint = CharField(max_length=32, null=True)
    width = IntegerField()
    height = IntegerField()
    thumb = CharField(max_length=500, null=True)

    class Meta:
        table_name = "upload_records"
        # 非唯一索引，和原来保持一致
        indexes = (
            (("etag",), False),
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
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "upload_task"
        indexes = (
            (("status", "created_at"), False),
        )


class UserInfo(BaseModel):
    """
    用户信息表

    - name: 用户姓名
    - user_number: 7 位数字的用户编号（唯一）
    """
    name = CharField(max_length=100)
    user_number = CharField(max_length=7, unique=True)

    class Meta:
        table_name = "user_info"
        indexes = (
            (("user_number",), True),  # user_number 唯一索引
        )


# =========================
# 连接 & 初始化函数
# =========================

def init_database_connection():
    """
    初始化当前进程的数据库连接（worker 执行）。
    兼容你原来的调用。
    """
    if db.is_closed():
        db.connect(reuse_if_open=True)


def close_database_connection():
    """
    关闭数据库连接
    """
    if not db.is_closed():
        db.close()


def init_wal_mode():
    """
    兼容旧接口：原来用于 SQLite WAL。
    现在换成 MySQL，只做一次连接检测和日志输出。
    """
    if db.is_closed():
        db.connect(reuse_if_open=True)
    log_line("[INFO] MySQL 数据库已连接（兼容原 init_wal_mode 调用）")


def create_tables_once():
    """
    老代码用的建表函数。
    这里扩展为：检查/创建所有相关表（如果不存在）。
    """
    init_database_connection()
    db.create_tables(
        [UploadRecord, UploadTask, UserInfo, File, UploadSession, UploadPart],
        safe=True,
    )
    log_line("[INFO] MySQL 数据库表结构检查/初始化完成")


if __name__ == '__main__':
    create_tables_once()
