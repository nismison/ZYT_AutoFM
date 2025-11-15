# db.py
import os

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


def init_database_connection():
    """
    初始化当前进程的数据库连接（worker 执行）。
    """
    if _db.is_closed():
        _db.connect(reuse_if_open=True)
        log_line(f"[PID {os.getpid()}] DB 连接建立完毕")


def init_wal_mode():
    """
    主进程设置 WAL（只需要一次）
    """
    _db.connect(reuse_if_open=True)
    _db.execute_sql("PRAGMA journal_mode=WAL;")
    log_line("[主进程] SQLite WAL 已启用")


def create_tables_once():
    """
    主进程建表
    """
    init_wal_mode()
    _db.create_tables([UploadRecord, UploadTask], safe=True)
    log_line("[主进程] 数据库表结构初始化完成")
