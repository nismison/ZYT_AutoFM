from datetime import datetime

import pymysql
from peewee import (
    Model,
    AutoField,
    CharField,
    BigIntegerField,
    IntegerField,
    DateTimeField,
    ForeignKeyField,
    BooleanField,
)

from config import db, TZ
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
    """
    文件主表：一条记录对应一个完整文件（通过 fingerprint 去重）

    本地分片实现中，字段含义：
      - fingerprint: 前端算好的文件指纹，用来做秒传 / 断点续传 / 去重
      - file_name: 用户原始文件名
      - file_size: 文件总大小（字节）
      - cos_key: 最终文件名（不带路径），实际文件路径为 IMMICH_EXTERNAL_HOST_ROOT / cos_key
      - status: 文件状态（例如 INIT / UPLOADING / COMPLETED），具体值由 config 中常量约定
      - url: 合并完成后给前端访问用的 URL（可选）
    """
    id = AutoField()

    fingerprint = CharField(max_length=64, unique=True, index=True)
    file_name = CharField(max_length=255)
    file_size = BigIntegerField()

    # 本地实现里不再是 COS key，而是最终文件名（例如 "<fingerprint>_original.mp4"）
    cos_key = CharField(max_length=512)

    # 具体取值由 config.FILE_STATUS_* 常量定义，这里不设默认值，全部在业务代码里显式赋值
    status = CharField(max_length=32, index=True)

    # worker 合并之后写入（比如 "/immich-external/<cos_key>"）
    url = CharField(max_length=1024, null=True)

    created_at = DateTimeField(default=datetime.now(TZ))
    updated_at = DateTimeField(default=datetime.now(TZ))

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now(TZ)
        return super().save(*args, **kwargs)

    class Meta:
        table_name = "file"  # 如果你原库不是这个表名，可以改成原来的


class UploadSession(BaseModel):
    """
    上传会话表：记录一次指纹/文件的“分片上传会话”

    字段含义：
      - file: 关联的 File 记录
      - upload_id: COS 时代用的，这里保留字段兼容（本地实现可以不使用）
      - chunk_size: 分片大小（字节）
      - total_chunks: 总分片数
      - uploaded_chunks: 已成功接收并记录到 UploadPart 的分片数量
      - status: 会话状态（UPLOADING / READY_TO_COMPLETE / COMPLETED 等）
    """
    id = AutoField()

    file = ForeignKeyField(
        File,
        backref="sessions",
        on_delete="CASCADE",
    )

    upload_id = CharField(max_length=255, null=True)  # 本地实现不用，可空

    chunk_size = IntegerField()
    total_chunks = IntegerField()
    uploaded_chunks = IntegerField(default=0)

    # 具体取值由 config.SESSION_STATUS_* 常量定义
    status = CharField(max_length=32, index=True)

    created_at = DateTimeField(default=datetime.now(TZ))
    updated_at = DateTimeField(default=datetime.now(TZ))

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now(TZ)
        return super().save(*args, **kwargs)

    class Meta:
        table_name = "upload_session"


class UploadPart(BaseModel):
    """
    分片表：记录每个分片的元数据

    字段含义：
      - file: 关联的 File 记录
      - part_number: 分片序号（从 1 开始）
      - etag: 这里用 MD5 摘要，便于后续排查问题（本地实现不用于 COS 校验）
      - status: 分片状态（目前逻辑里只用 "DONE"）
    """
    id = AutoField()

    file = ForeignKeyField(
        File,
        backref="parts",
        on_delete="CASCADE",
    )

    part_number = IntegerField()
    etag = CharField(max_length=64)
    status = CharField(max_length=32, index=True)

    created_at = DateTimeField(default=datetime.now(TZ))

    class Meta:
        table_name = "upload_part"
        indexes = (
            # 唯一索引：同一 file 下的同一个 part_number 只能有一条记录
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
    upload_time = DateTimeField(default=datetime.now(TZ))
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
    id = AutoField()
    tmp_path = CharField(max_length=500)  # 临时文件完整路径
    etag = CharField(max_length=32)  # 前端传入的校验
    fingerprint = CharField(max_length=32)
    original_filename = CharField(max_length=255)
    device = CharField(max_length=100)
    external_rel_path = CharField(max_length=500, null=True)
    suffix = CharField(max_length=10)  # 文件扩展名（.jpg/.png/.mp4）
    status = CharField(max_length=20, default="pending")
    # 状态：pending / processing / done / failed

    retry = IntegerField(default=0)  # 重试次数
    created_at = DateTimeField(default=datetime.now(TZ))
    updated_at = DateTimeField(default=datetime.now(TZ))

    class Meta:
        table_name = "upload_task"
        indexes = (
            (("status", "created_at"), False),
        )


class UserInfo(BaseModel):
    """
    用户信息表
    """
    id = AutoField()
    name = CharField(max_length=100)
    user_number = CharField(max_length=7, unique=True)
    token = CharField(max_length=500, null=True)
    baichuan_token = CharField(max_length=500, null=True)
    cos_token = CharField(max_length=2000, null=True)
    phone = CharField(max_length=11, null=True)
    device_model = CharField(max_length=50, null=True)
    device_id = CharField(max_length=50, null=True)
    token_expires = IntegerField(null=True)
    baichuan_expires = IntegerField(null=True)

    class Meta:
        table_name = "user_info"
        indexes = (
            (("user_number",), True),  # user_number 唯一索引
        )


class UserTemplatePic(BaseModel):
    """
    用户模板图片表 (精简工程化版本)
    支持 User -> Category -> SubCategory -> Sequence 结构下的多图存储
    """
    id = AutoField()

    # 业务查询核心字段
    user_number = CharField(max_length=20, index=True)
    category = CharField(max_length=50)  # 如: 4L2R, DYL
    sub_category = CharField(max_length=50, default="")  # 如: A1, A2; 无子类则为空
    sequence = CharField(max_length=20)  # 如: 1, 2, 3

    # 资源链接
    cos_url = CharField(max_length=1024)

    # 审计字段
    created_at = DateTimeField(default=datetime.now(TZ))

    class Meta:
        table_name = "user_template_pics"
        indexes = (
            # 复合索引，极大提升“按逻辑路径筛选”的查询速度
            (('user_number', 'category', 'sub_category', 'sequence'), False),
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
