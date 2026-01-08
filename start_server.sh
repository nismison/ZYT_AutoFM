#!/usr/bin/env bash

# start_server.sh
# 仅负责“启动当前版本的服务”，不做 git pull：
# 1. 执行 db.py 初始化数据库
# 2. 重启 upload_worker.py
# 3. 重启 merge_worker.py
# 4. 启动 Gunicorn（后台运行 + 健康检查）
# 5. 回显各服务 PID，供 CI/监控解析

set -euo pipefail

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# ============================
# 基本路径配置
# ============================
REPO_PATH="/root/ZYT_AutoFM"

VENV_PY="/www/server/pyporject_evn/versions/3.10.19/bin/python"
GUNICORN_BIN="/www/server/pyporject_evn/versions/3.10.19/bin/gunicorn"
GUNICORN_CONF="$REPO_PATH/gunicorn_conf.py"
APP_MODULE="flask_server:app"

# 日志路径
WORKER_LOG="/root/ZYT_AutoFM/upload_worker.log"
MERGE_WORKER_LOG="/root/ZYT_AutoFM/merge_worker.log"
GUNICORN_LOG="/root/ZYT_AutoFM/gunicorn.log"
CHECKIN_SERVER_LOG="/root/ZYT_AutoFM/checkin_server.log"

log "[INFO] 当前执行用户: $(whoami)"

cd "$REPO_PATH" || {
  log "[ERROR] 无法切换到项目目录: $REPO_PATH"
  exit 1
}

# ============================
# 1. 初始化数据库（db.py）
# ============================
log "[INFO] 执行 db.py 初始化数据库..."

if ! "$VENV_PY" "$REPO_PATH/db.py"; then
  log "[ERROR] 数据库初始化失败（db.py 返回非 0），终止启动。"
  exit 1
fi

log "[INFO] 数据库初始化完成。"

# ============================
# 2. 启动 upload_worker.py（后台）
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
  nohup "$VENV_PY" -u "$WORKER_SCRIPT" >> "$WORKER_LOG" 2>&1 &
  UPLOAD_WORKER_PID=$!
  log "[INFO] upload_worker.py 已在后台启动，PID: $UPLOAD_WORKER_PID"
  echo "UPLOAD_WORKER_PID=$UPLOAD_WORKER_PID"
else
  log "[WARNING] 未找到 $WORKER_SCRIPT，跳过上传 Worker 启动。"
fi

# ============================
# 3. 启动 merge_worker.py（后台）
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
  nohup "$VENV_PY" -u "$MERGE_WORKER_SCRIPT" >> "$MERGE_WORKER_LOG" 2>&1 &
  MERGE_WORKER_PID=$!
  log "[INFO] merge_worker.py 已在后台启动，PID: $MERGE_WORKER_PID"
  echo "MERGE_WORKER_PID=$MERGE_WORKER_PID"
else
  log "[WARNING] 未找到 $MERGE_WORKER_SCRIPT，跳过 Merge Worker 启动。"
fi

# ============================
# 3.5 启动 checkin_server.py（后台）
# ============================
CHECKIN_SERVER_SCRIPT="$REPO_PATH/checkin_server.py"
CHECKIN_SERVER_PID=""

if [ -f "$CHECKIN_SERVER_SCRIPT" ]; then
  log "[INFO] 检查 checkin_server.py 是否已在运行..."

  CHECKIN_EXISTING_PIDS=$(pgrep -f "$CHECKIN_SERVER_SCRIPT" || true)

  if [ -n "$CHECKIN_EXISTING_PIDS" ]; then
    log "[INFO] 检测到运行中的 checkin_server.py，PIDs: $CHECKIN_EXISTING_PIDS，准备重启..."

    kill $CHECKIN_EXISTING_PIDS 2>/dev/null || true
    sleep 2

    CHECKIN_STILL_PIDS=$(pgrep -f "$CHECKIN_SERVER_SCRIPT" || true)
    if [ -n "$CHECKIN_STILL_PIDS" ]; then
      log "[WARN] 进程未完全退出，执行 kill -9: $CHECKIN_STILL_PIDS"
      kill -9 $CHECKIN_STILL_PIDS 2>/dev/null || true
      sleep 1
    fi
  else
    log "[INFO] 未发现运行中的 checkin_server.py，直接启动。"
  fi

  log "[INFO] 启动后台 Checkin Server: $CHECKIN_SERVER_SCRIPT"
  mkdir -p "$(dirname "$CHECKIN_SERVER_LOG")"
  nohup "$VENV_PY" -u "$CHECKIN_SERVER_SCRIPT" >> "$CHECKIN_SERVER_LOG" 2>&1 &
  CHECKIN_SERVER_PID=$!
  log "[INFO] checkin_server.py 已在后台启动，PID: $CHECKIN_SERVER_PID"
  echo "CHECKIN_SERVER_PID=$CHECKIN_SERVER_PID"
else
  log "[WARNING] 未找到 $CHECKIN_SERVER_SCRIPT，跳过 Checkin Server 启动。"
fi

# ============================
# 4. 启动 Gunicorn（后台 + 清理旧进程）
# ============================

log "[INFO] 清理旧的 gunicorn 进程..."
# 匹配项目模块名，而不是配置文件名
OLD_GUNICORN_PIDS=$(pgrep -f "gunicorn.*ZYT_AutoFM.*flask_server:app" || true)

if [ -n "$OLD_GUNICORN_PIDS" ]; then
  log "[INFO] 发现旧 gunicorn 进程: $OLD_GUNICORN_PIDS，准备终止"
  kill $OLD_GUNICORN_PIDS 2>/dev/null || true
  sleep 2
  STILL_PIDS=$(pgrep -f "gunicorn.*ZYT_AutoFM.*flask_server:app" || true)
  if [ -n "$STILL_PIDS" ]; then
    log "[WARN] gunicorn 未完全退出，执行 kill -9: $STILL_PIDS"
    kill -9 $STILL_PIDS 2>/dev/null || true
    sleep 1
  fi
else
  log "[INFO] 未发现运行中的 gunicorn"
fi

log "[INFO] 启动新的 gunicorn 实例..."
mkdir -p "$(dirname "$GUNICORN_LOG")"
nohup "$GUNICORN_BIN" -c "$GUNICORN_CONF" "$APP_MODULE" >> "$GUNICORN_LOG" 2>&1 &
GUNICORN_PID=$!
sleep 3

# 健康检查
if ! kill -0 "$GUNICORN_PID" 2>/dev/null; then
  log "[ERROR] gunicorn 启动失败，PID=$GUNICORN_PID, 查看日志: $GUNICORN_LOG"
  echo "GUNICORN_PID=0"
  exit 1
fi

log "[INFO] gunicorn 启动成功，master PID=$GUNICORN_PID"
echo "GUNICORN_PID=$GUNICORN_PID"

log "[INFO] 启动流程完成。所有服务已在后台运行。"
