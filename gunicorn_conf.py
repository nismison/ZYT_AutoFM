# gunicorn_conf.py
# 仅用于配置 Gunicorn 参数，不做任何业务逻辑

# 项目目录
chdir = '/www/dk_project/dk_app/qinglong/QingLong/data/scripts/ZYT_AutoFM'

# worker 数量（根据 CPU 核心数和实际负载调节）
workers = 4

# 每个 worker 的线程数（I/O 型任务可以适当多一点）
threads = 4

# 不强制指定 user，保持当前启动用户（deploy）
# user = 'deploy'

# 启动模式：sync 足够，后续需要再改 gevent/uvicorn_worker
worker_class = 'sync'

# 绑定地址：只监听本机 5001，交给 Nginx 反代
bind = '127.0.0.1:5001'

# PID 文件
pidfile = '/www/dk_project/dk_app/qinglong/QingLong/data/scripts/ZYT_AutoFM/gunicorn.pid'

# 日志路径
accesslog = '/www/wwwlogs/python/ZYT_AutoFM/gunicorn_access.log'
errorlog = '/www/wwwlogs/python/ZYT_AutoFM/gunicorn_error.log'

# 日志级别
loglevel = 'info'

# ============================
# 健壮性配置
# ============================

# 单个请求最大处理时间，超时会杀掉 worker 重启
timeout = 30
graceful_timeout = 30

# 防止 worker 跑太久内存泄漏：达到一定请求数后自动重启
max_requests = 1000
max_requests_jitter = 100
