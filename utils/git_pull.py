import subprocess

from utils.logger import log_line


def git_pull():
    """
        Gunicorn 启动时强制拉取最新代码，丢弃本地修改。

        :param server: Gunicorn server 对象
        :returns: None
        :raises keyError: 无
        """

    repo_path = '/root/ZYT_AutoFM'

    # 强制覆盖本地的标准命令组合
    cmd = (
        f"cd {repo_path} && "
        "git reset --hard HEAD && "
        "git clean -fd && "
        "git fetch --all && "
        "git reset --hard origin/master"
    )

    log_line("[INFO] Gunicorn Master 启动：强制同步最新代码（丢弃本地修改）...")

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
            log_line(f"[ERROR] Git 强制拉取失败：{stderr or stdout}")
        else:
            log_line("[INFO] 代码已成功强制同步至最新版本")
            if stdout:
                log_line(stdout)

    except subprocess.TimeoutExpired:
        log_line("[WARNING] Git 拉取超时，跳过更新")

    except Exception as e:
        log_line(f"[ERROR] 强制拉取更新出现异常：{e}")