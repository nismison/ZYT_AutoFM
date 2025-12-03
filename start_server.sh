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
  nohup "$VENV_PY" "$WORKER_SCRIPT" >> "$WORKER_LOG" 2>&1 &
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
  nohup "$VENV_PY" "$MERGE_WORKER_SCRIPT" >> "$MERGE_WORKER_LOG" 2>&1 &
  MERGE_WORKER_PID=$!
  log "[INFO] merge_worker.py 已在后台启动，PID: $MERGE_WORKER_PID"
  echo "MERGE_WORKER_PID=$MERGE_WORKER_PID"
else
  log "[WARNING] 未找到 $MERGE_WORKER_SCRIPT，跳过 Merge Worker 启动。"
fi

# ============================
# 4. 启动 Gunicorn（后台 + 清理旧进程 + 健康检查）
# ============================

GUNICORN_PIDFILE="$REPO_PATH/gunicorn.pid"

# 4.1 确认配置文件存在
if [ ! -f "$GUNICORN_CONF" ]; then
  log "[ERROR] Gunicorn 配置文件不存在，GUNICORN_CONF 实际值为: $(printf '%q\n' "$GUNICORN_CONF")"
  echo "GUNICORN_PID=0"
  exit 1
fi

# 4.2 如果存在旧的 Gunicorn（通过 pidfile），先优雅停止
if [ -f "$GUNICORN_PIDFILE" ]; then
  OLD_PID="$(cat "$GUNICORN_PIDFILE" 2>/dev/null || echo "")"

  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    log "[INFO] 检测到已运行的 Gunicorn（PID=$OLD_PID），准备重启..."

    # 优雅停止
    kill "$OLD_PID" 2>/dev/null || true

    # 最多等 10 秒让它退出
    for i in {1..10}; do
      if kill -0 "$OLD_PID" 2>/dev/null; then
        sleep 1
      else
        break
      fi
    done

    # 如果还活着，强制 kill -9
    if kill -0 "$OLD_PID" 2>/dev/null; then
      log "[WARN] Gunicorn 仍在运行，执行 kill -9 $OLD_PID"
      kill -9 "$OLD_PID" 2>/dev/null || true
      sleep 1
    fi
  else
    log "[INFO] 发现旧的 pidfile 但进程不存在，清理 pidfile。"
  fi

  # 清理掉旧 pidfile（避免 gunicorn 拿到坏 pid）
  rm -f "$GUNICORN_PIDFILE" 2>/dev/null || true
fi

# 4.3 启动新的 Gunicorn（后台）
log "[INFO] 以后台方式启动 Gunicorn 服务..."
log "[INFO] 命令: $GUNICORN_BIN -c $GUNICORN_CONF $APP_MODULE"

mkdir -p "$(dirname "$GUNICORN_LOG")"

nohup "$GUNICORN_BIN" -c "$GUNICORN_CONF" "$APP_MODULE" >> "$GUNICORN_LOG" 2>&1 &
GUNICORN_PID=$!
sleep 3

# 4.4 健康检查：确认新 Gunicorn 还在跑
if ! kill -0 "$GUNICORN_PID" 2>/dev/null; then
  log "[ERROR] Gunicorn 启动失败，PID: $GUNICORN_PID，详情见日志: $GUNICORN_LOG"
  echo "GUNICORN_PID=0"
  exit 1
fi

log "[INFO] Gunicorn 已在后台启动，PID: $GUNICORN_PID"
echo "GUNICORN_PID=$GUNICORN_PID"

log "[INFO] 启动流程完成。所有服务已在后台运行。"
