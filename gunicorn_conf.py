# gunicorn_conf.py
# 仅用于配置 Gunicorn 参数，不做任何业务逻辑 / git / 建表操作

# 项目目录
chdir = '/www/dk_project/dk_app/qinglong/QingLong/data/scripts/ZYT_AutoFM'

# worker 数量（根据 CPU 核心数和实际负载调节）
workers = 4

# 每个 worker 内部的线程数（对于 I/O 型任务可以适当增加）
threads = 4

# 运行用户
user = 'www'

# 启动模式：sync 足够，后面如果要 gevent/uvicorn_worker 再改
worker_class = 'sync'

# 绑定地址
bind = '0.0.0.0:5001'

# PID 文件（用于停止 / 重启）
pidfile = '/www/dk_project/dk_app/qinglong/QingLong/data/scripts/ZYT_AutoFM/gunicorn.pid'

# 日志路径
accesslog = '/www/wwwlogs/python/ZYT_AutoFM/gunicorn_acess.log'
errorlog = '/www/wwwlogs/python/ZYT_AutoFM/gunicorn_error.log'

# 日志级别
loglevel = 'info'

# ============================
# 一些推荐的健壮性配置
# ============================

# 单个请求最大处理时间，超时会杀掉 worker 重启，防止长时间阻塞
timeout = 30
graceful_timeout = 30

# 防止 worker 跑太久内存泄漏：到达一定请求数后自动重启
max_requests = 1000
max_requests_jitter = 100
