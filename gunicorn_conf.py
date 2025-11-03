import subprocess

# 项目目录
chdir = '/www/dk_project/dk_app/qinglong/QingLong/data/scripts/ZYT_AutoFM'

# 指定进程数
workers = 5

# 指定每个进程开启的线程数
threads = 5

# 启动用户
user = 'www'

# 启动模式
worker_class = 'sync'

# 绑定的ip与端口
bind = '0.0.0.0:5001'

# 设置进程文件目录（用于停止服务和重启服务，请勿删除）
pidfile = '/www/dk_project/dk_app/qinglong/QingLong/data/scripts/ZYT_AutoFM/gunicorn.pid'

# 设置访问日志和错误信息日志路径
accesslog = '/www/wwwlogs/python/ZYT_AutoFM/gunicorn_acess.log'
errorlog = '/www/wwwlogs/python/ZYT_AutoFM/gunicorn_error.log'

# 日志级别，这个日志级别指的是错误日志的级别，而访问日志的级别无法设置
# debug:调试级别，记录的信息最多；
# info:普通级别；
# warning:警告消息；
# error:错误消息；
# critical:严重错误消息；
loglevel = 'info'


# 自定义设置项请写到该处
# 最好以上面相同的格式 <注释 + 换行 + key = value> 进行书写， 
# PS: gunicorn 的配置文件是python扩展形式，即".py"文件，需要注意遵从python语法，
# 如：loglevel的等级是字符串作为配置的，需要用引号包裹起来

# =========================================================
# 🔧 自定义启动钩子：Gunicorn Master 启动时自动拉取最新代码
# =========================================================


def on_starting(server):
    """
    仅在 Gunicorn master 启动时执行（不会在每个 worker 执行），
    用于自动拉取最新代码。
    """
    repo_path = '/www/dk_project/dk_app/qinglong/QingLong/data/scripts/ZYT_AutoFM'
    cmd = f"cd {repo_path} && git pull"

    server.log.info("🚀 Gunicorn Master 启动中：正在检测并拉取最新代码 ...")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            server.log.error("❌ Git 拉取失败：")
            server.log.info(stderr or stdout)
        else:
            if "Already up to date" in stdout or "已经是最新的" in stdout:
                server.log.info("✅ 代码已是最新，无需更新")
            else:
                server.log.info("✅ Git 拉取成功：")
                server.log.info(stdout)
    except subprocess.TimeoutExpired:
        server.log.error("⚠️ Git 拉取超时，跳过更新")
    except Exception as e:
        server.log.error("❌ 拉取更新时出现异常：", e)
