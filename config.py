import logging.config
import os

from dotenv import load_dotenv
from peewee import MySQLDatabase

from utils.ip_address import get_real_lan_ip
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")

load_dotenv()
IS_DEV = os.getenv("ENV") == "dev"

LOG_PATH = "/root/ZYT_AutoFM/gunicorn_error.log"

# ==================== 自动工单配置 ====================
BASE_URL = f"http://{get_real_lan_ip()}:5001" if IS_DEV else "https://api.zytsy.icu"

FM_BASE_URL = "https://chuanplus-client.onewo.com/api/client"
# 转发接口
TARGET_BASE = "https://gw.4009515151.com"

HEADERS_BASE = {
    "Content-Type": "application/json",
    "x-tenant": "10010",
}

# ==================== 青龙配置 ====================
QL_BASE_URL = "http://ql.zytsy.icu"
QL_CLIENT_ID = "i-v-Y0pCCP1m"
QL_CLIENT_SECRET = "l0_EIhFAT-m2EkvA3IdK3L6I"
# ==================== immich配置 ====================
IMMICH_API_KEY = '9zYuNvGF9ZGTOrqULYL5hoWc6JfRBx7wdN44tdb2w'
IMMICH_URL = 'https://immich.zytsy.icu/api'
# 宿主机上 External Library 对应的真实路径（你的服务看到的是这个）
IMMICH_EXTERNAL_HOST_ROOT = "/immich-external-library"
# Immich 容器里看到的同一目录路径（External Library Import Path 配的就是它）
IMMICH_EXTERNAL_CONTAINER_ROOT = "/external"
# 在 Immich 管理界面创建的 External Library 的 ID
IMMICH_LIBRARY_ID = "f38fff60-df57-42e6-bfdc-e6164778714a"
# 目标相册 ID（你原来写死的那个）
IMMICH_TARGET_ALBUM_ID = "fa588b80-6b40-4607-8d6c-cd90101db9e9"

# 相册图片存储目录（持久保存）
GALLERY_STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'gallery')
# 缓存图片存储目录（持久保存）
GALLERY_CACHE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'gallery_cache')
# 水印图片存储目录（定时清理）
WATERMARK_STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'watermark')

# =========================
# MySQL / Peewee 配置
# =========================

MYSQL_DB_NAME = os.getenv("MYSQL_DB_NAME", "uploads")
MYSQL_DB_USER = os.getenv("MYSQL_DB_USER", "root")
MYSQL_DB_PASSWORD = os.getenv("MYSQL_DB_PASSWORD", "lzz22222222")
MYSQL_DB_HOST = os.getenv("MYSQL_DB_HOST", "43.251.227.18")
MYSQL_DB_PORT = int(os.getenv("MYSQL_DB_PORT", "3306"))

db = MySQLDatabase(
    MYSQL_DB_NAME,
    user=MYSQL_DB_USER,
    password=MYSQL_DB_PASSWORD,
    host=MYSQL_DB_HOST,
    port=MYSQL_DB_PORT,
    charset="utf8mb4",
)

# =========================
# COS / STS 配置
# =========================

# QL 环境变量 key，可按需改成别的名字
COS_STS_ENV_KEY = "COS_STS"

# =========================
# 分片上传相关常量
# =========================
# 文件状态
FILE_STATUS_INIT = "INIT"
FILE_STATUS_UPLOADING = "UPLOADING"
FILE_STATUS_COMPLETED = "COMPLETED"

# 会话状态
SESSION_STATUS_UPLOADING = "UPLOADING"
SESSION_STATUS_READY_TO_COMPLETE = "READY_TO_COMPLETE"
SESSION_STATUS_COMPLETED = "COMPLETED"

# ==================== 日志配置 ====================
LOGGING_CONFIG = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',  # 确保处理器级别是 INFO
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',  # 确保根日志器级别是 INFO
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)
