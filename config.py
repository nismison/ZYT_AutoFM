import os
import logging.config
from dotenv import load_dotenv

load_dotenv()
IS_DEV = os.getenv("ENV") == "dev"

# ==================== 自动工单配置 ====================
# 基础 Token (从环境变量读取)
BASIC_TOKEN = os.getenv("ZYT_TOKEN") or \
              "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJBQ0NFU1NfVE9LRU4iLCJjbGllbnRJZCI6IjVlOTZlYWMwNjE1MWQwY2UyZGQ5NTU0ZDdlZTE2N2NlIiwic2NvcGUiOiJhbGwgci1zdGFmZiIsInRva2VuIjoiMjQwOTg0MCIsImlhdCI6MTc2MjA2MjE0OCwiZXhwIjoxNzYyNjY2OTQ4fQ.RJZklvpDkWq_tLBCFDXl2sIz3tl4ul3lkDBYgk-Z8n8"

FM_BASE_URL = "https://chuanplus-client.onewo.com/api/client"
# 转发接口
TARGET_BASE = "https://gw.4009515151.com"

HEADERS_BASE = {
    "Content-Type": "application/json",
    "x-tenant": "10010",
}

# ==================== 图库本地存储配置 ====================
if IS_DEV:
    # 开发环境
    BASE_URL = "http://192.168.245.233:5001"
    IMMICH_URL = 'https://immich.zytsy.icu/api'
else:
    # 正式环境
    BASE_URL = "https://api.zytsy.icu"
    IMMICH_URL = 'http://127.0.0.1:2283/api'

# ==================== immich配置 ====================
IMMICH_API_KEY = '9zYuNvGF9ZGTOrqULYL5hoWc6JfRBx7wdN44tdb2w'

# 相册图片存储目录（持久保存）
GALLERY_STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'gallery')
# 缓存图片存储目录（持久保存）
GALLERY_CACHE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'gallery_cache')
# 水印图片存储目录（定时清理）
WATERMARK_STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'watermark')

LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
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
