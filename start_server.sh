#!/usr/bin/env bash

# start_server.sh
# 用于部署 / 启动 ZYT_AutoFM：
# 1. 强制同步最新代码（丢弃本地修改）
# 2. 通过 db.py 初始化数据库
# 3. 启动后台上传 Worker（upload_worker.py）
# 4. 启动 Gunicorn

set -euo pipefail

# ============================
# 日志工具函数（带时间戳）
# ============================
log() {
  # 用法：log "[INFO] xxxx"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# ============================
# 基本路径配置（按需修改）
# ============================
REPO_PATH="/www/dk_project/dk_app/qinglong/QingLong/data/scripts/ZYT_AutoFM"
VENV_PY="/www/server/pyporject_evn/3820/bin/python3.8"
GUNICORN_BIN="/www/server/pyporject_evn/3820/bin/gunicorn"
GUNICORN_CONF="$REPO_PATH/gunicorn_conf.py"
APP_MODULE="flask_server:app"

# 日志路径
WORKER_LOG="/www/wwwlogs/python/ZYT_AutoFM/upload_worker.log"

log "[INFO] 当前执行用户: $(whoami)"

cd "$REPO_PATH" || {
  log "[ERROR] 无法切换到项目目录: $REPO_PATH"
  exit 1
}

# ============================
# 1. 强制同步最新代码（丢弃本地修改）
# ============================
log "[INFO] 开始强制同步最新代码（丢弃本地修改）..."

GIT_CMD="
git reset --hard HEAD && \
git clean -fd && \
git fetch --all && \
git reset --hard origin/master
"

# 使用 timeout 防止 git 卡死，失败时给出提示但不直接退出
if ! timeout 30s bash -lc "$GIT_CMD"; then
  log "[WARNING] Git 强制拉取失败或超时，将继续使用当前代码版本。"
else
  log "[INFO] 代码已成功强制同步至 origin/master。"
fi

# ============================
# 2. 初始化数据库（执行 db.py）
# ============================
log "[INFO] 执行 db.py 初始化数据库..."

if ! "$VENV_PY" "$REPO_PATH/db.py"; then
  log "[ERROR] 数据库初始化失败（db.py 返回非 0），终止启动。"
  exit 1
fi

log "[INFO] 数据库初始化完成。"

# ============================
# 3. 启动后台上传 Worker（upload_worker.py）
#    - 基于 REPO_PATH
#    - 简单去重：已在跑则不重复启动
# ============================
WORKER_SCRIPT="$REPO_PATH/upload_worker.py"

if [ -f "$WORKER_SCRIPT" ]; then
  log "[INFO] 检查 upload_worker.py 是否已在运行..."

  # pgrep -f 会匹配完整命令行，这里用绝对路径降低误伤概率
  EXISTING_PIDS=$(pgrep -f "$WORKER_SCRIPT" || true)

  if [ -n "$EXISTING_PIDS" ]; then
    log "[INFO] 检测到运行中的 upload_worker.py，PIDs: $EXISTING_PIDS，跳过启动。"
  else
    log "[INFO] 启动后台上传 Worker: $WORKER_SCRIPT"
    mkdir -p "$(dirname "$WORKER_LOG")"
    nohup "$VENV_PY" "$WORKER_SCRIPT" >> "$WORKER_LOG" 2>&1 &
    log "[INFO] upload_worker.py 已在后台启动，PID: $!"
  fi
else
  log "[WARNING] 未找到 $WORKER_SCRIPT，跳过上传 Worker 启动。"
fi

# ============================
# 4. 启动 Gunicorn
# ============================
log "[INFO] 启动 Gunicorn 服务..."
log "[INFO] 命令: $GUNICORN_BIN -c $GUNICORN_CONF $APP_MODULE"

# 使用 exec 替换当前 shell 进程，方便守护进程 / 宝塔管理
exec "$GUNICORN_BIN" -c "$GUNICORN_CONF" "$APP_MODULE"
