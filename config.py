import os
import logging.config
from dotenv import load_dotenv

from utils.ip_address import get_real_lan_ip

load_dotenv()
IS_DEV = os.getenv("ENV") == "dev"

# ==================== 自动工单配置 ====================
BASE_URL = f"http://{get_real_lan_ip()}:5001" if IS_DEV else "https://api.zytsy.icu"
# 基础 Token (从环境变量读取)
BASIC_TOKEN = os.getenv("ZYT_TOKEN", "")

FM_BASE_URL = "https://chuanplus-client.onewo.com/api/client"
# 转发接口
TARGET_BASE = "https://gw.4009515151.com"
BAICHUAN_BASE = "https://chuanplus-client.onewo.com"

HEADERS_BASE = {
    "Content-Type": "application/json",
    "x-tenant": "10010",
}

# ==================== 青龙配置 ====================
QL_BASE_URL = "http://ql.zytsy.icu" if IS_DEV else "http://127.0.0.1:15700"
QL_CLIENT_ID = "i-v-Y0pCCP1m"
QL_CLIENT_SECRET = "l0_EIhFAT-m2EkvA3IdK3L6I"
# ==================== immich配置 ====================
IMMICH_API_KEY = '9zYuNvGF9ZGTOrqULYL5hoWc6JfRBx7wdN44tdb2w'
IMMICH_URL = 'https://immich.zytsy.icu/api' if IS_DEV else 'http://127.0.0.1:2283/api'

# 相册图片存储目录（持久保存）
GALLERY_STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'gallery')
# 缓存图片存储目录（持久保存）
GALLERY_CACHE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'gallery_cache')
# 水印图片存储目录（定时清理）
WATERMARK_STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'watermark')

# ==================== 日志配置 ====================
LOG_PATH = "./gunicorn_error.log" if IS_DEV else "/www/wwwlogs/python/ZYT_AutoFM/gunicorn_error.log"
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
