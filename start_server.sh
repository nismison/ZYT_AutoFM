#!/usr/bin/env bash

# start_server.sh
# 用于部署 / 启动 ZYT_AutoFM：
# 1. 强制同步最新代码（丢弃本地修改）
# 2. 通过 db.py 初始化数据库
# 3. 启动后台上传 Worker（upload_worker.py）
# 4. 启动后台 Merge Worker（merge_worker.py）
# 5. 启动 Gunicorn（后台运行）
#
# 特别说明：
# - git 拉取失败 / 超时会直接退出（exit 1）
# - 所有服务以后台方式运行
# - 脚本会 echo 出：
#     UPLOAD_WORKER_PID=<pid>
#     MERGE_WORKER_PID=<pid>
#     GUNICORN_PID=<pid>
#   供 CI 解析并写入通知

set -euo pipefail

# ============================
# 日志工具函数（带时间戳）
# ============================
log() {
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
MERGE_WORKER_LOG="/www/wwwlogs/python/ZYT_AutoFM/merge_worker.log"
GUNICORN_LOG="/www/wwwlogs/python/ZYT_AutoFM/gunicorn.log"

log "[INFO] 当前执行用户: $(whoami)"

cd "$REPO_PATH" || {
  log "[ERROR] 无法切换到项目目录: $REPO_PATH"
  exit 1
}

# ============================
# 1. 同步最新代码
# ============================
log "[INFO] 开始同步最新代码..."

GIT_CMD="git pull"

# 使用 timeout 防止 git 卡死，失败时直接终止部署
if ! timeout 30s bash -lc "$GIT_CMD"; then
  log "[ERROR] Git 拉取失败或超时，终止部署。"
  exit 1
fi

log "[INFO] 代码已成功更新到最新。"

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
# ============================
WORKER_SCRIPT="$REPO_PATH/upload_worker.py"
UPLOAD_WORKER_PID=""

if [ -f "$WORKER_SCRIPT" ]; then
  log "[INFO] 检查 upload_worker.py 是否已在运行..."

  EXISTING_PIDS=$(pgrep -f "$WORKER_SCRIPT" || true)

  if [ -n "$EXISTING_PIDS" ]; then
    log "[INFO] 检测到运行中的 upload_worker.py，PIDs: $EXISTING_PIDS，准备重启..."

    kill $EXISTING_PIDS 2>/dev/null || true
    sleep 2

    STILL_PIDS=$(pgrep -f "$WORKER_SCRIPT" || true)
    if [ -n "$STILL_PIDS" ]; then
      log "[WARN] 进程未完全退出，执行 kill -9: $STILL_PIDS"
      kill -9 $STILL_PIDS 2>/dev/null || true
      sleep 1
    fi
  else
    log "[INFO] 未发现运行中的 upload_worker.py，直接启动。"
  fi

  log "[INFO] 启动后台上传 Worker: $WORKER_SCRIPT"
  mkdir -p "$(dirname "$WORKER_LOG")"
  nohup "$VENV_PY" "$WORKER_SCRIPT" >> "$WORKER_LOG" 2>&1 &
  UPLOAD_WORKER_PID=$!
  log "[INFO] upload_worker.py 已在后台启动，PID: $UPLOAD_WORKER_PID"
  # 供 CI 解析
  echo "UPLOAD_WORKER_PID=$UPLOAD_WORKER_PID"
else
  log "[WARNING] 未找到 $WORKER_SCRIPT，跳过上传 Worker 启动。"
fi

# ============================
# 4. 启动后台 Merge Worker（merge_worker.py）
# ============================
MERGE_WORKER_SCRIPT="$REPO_PATH/merge_worker.py"
MERGE_WORKER_PID=""

if [ -f "$MERGE_WORKER_SCRIPT" ]; then
  log "[INFO] 检查 merge_worker.py 是否已在运行..."

  MERGE_EXISTING_PIDS=$(pgrep -f "$MERGE_WORKER_SCRIPT" || true)

  if [ -n "$MERGE_EXISTING_PIDS" ]; then
    log "[INFO] 检测到运行中的 merge_worker.py，PIDs: $MERGE_EXISTING_PIDS，准备重启..."

    kill $MERGE_EXISTING_PIDS 2>/dev/null || true
    sleep 2

    MERGE_STILL_PIDS=$(pgrep -f "$MERGE_WORKER_SCRIPT" || true)
    if [ -n "$MERGE_STILL_PIDS" ]; then
      log "[WARN] 进程未完全退出，执行 kill -9: $MERGE_STILL_PIDS"
      kill -9 $MERGE_STILL_PIDS 2>/dev/null || true
      sleep 1
    fi
  else
    log "[INFO] 未发现运行中的 merge_worker.py，直接启动。"
  fi

  log "[INFO] 启动后台 Merge Worker: $MERGE_WORKER_SCRIPT"
  mkdir -p "$(dirname "$MERGE_WORKER_LOG")"
  nohup "$VENV_PY" "$MERGE_WORKER_SCRIPT" >> "$MERGE_WORKER_LOG" 2>&1 &
  MERGE_WORKER_PID=$!
  log "[INFO] merge_worker.py 已在后台启动，PID: $MERGE_WORKER_PID"
  echo "MERGE_WORKER_PID=$MERGE_WORKER_PID"
else
  log "[WARNING] 未找到 $MERGE_WORKER_SCRIPT，跳过 Merge Worker 启动。"
fi

# ============================
# 5. 启动 Gunicorn（后台方式）
# ============================
log "[INFO] 以后台方式启动 Gunicorn 服务..."
log "[INFO] 命令: $GUNICORN_BIN -c $GUNICORN_CONF $APP_MODULE"

mkdir -p "$(dirname "$GUNICORN_LOG")"
nohup "$GUNICORN_BIN" -c "$GUNICORN_CONF" "$APP_MODULE" >> "$GUNICORN_LOG" 2>&1 &
GUNICORN_PID=$!
log "[INFO] Gunicorn 已在后台启动，PID: $GUNICORN_PID"
# 供 CI 解析
echo "GUNICORN_PID=$GUNICORN_PID"

log "[INFO] 部署流程完成。所有服务已在后台运行。"
