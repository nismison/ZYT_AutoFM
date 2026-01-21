#!/usr/bin/env bash

# start_server.sh
# 仅负责“启动当前版本的服务”，不做 git pull：
# 1. 执行 db.py 初始化数据库
# 2. 重启各 worker（upload/merge/checkin/refresh_token 等）
# 3. 启动 Gunicorn（后台运行 + 健康检查）
# 4. 回显各服务 PID，供 CI/监控解析

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

# ============================
# 通用：优雅停止 + 必要时强杀
# ============================
kill_by_pids() {
  local pids="$1"
  if [ -z "$pids" ]; then
    return 0
  fi

  kill $pids 2>/dev/null || true
  sleep 2

  # 再次检查是否还存在
  local still=""
  for pid in $pids; do
    if kill -0 "$pid" 2>/dev/null; then
      still="$still $pid"
    fi
  done

  if [ -n "${still// }" ]; then
    log "[WARN] 进程未完全退出，执行 kill -9:${still}"
    kill -9 $still 2>/dev/null || true
    sleep 1
  fi
}

# ============================
# 通用：重启一个 python 后台服务
# 参数：
#   1) name        用于日志与输出变量名（例如 UPLOAD_WORKER）
#   2) script_path 脚本绝对路径
#   3) log_path    日志文件绝对路径
# ============================
restart_python_daemon() {
  local name="$1"
  local script_path="$2"
  local log_path="$3"

  if [ ! -f "$script_path" ]; then
    log "[WARNING] 未找到 $script_path，跳过 ${name} 启动。"
    echo "${name}_PID=0"
    return 0
  fi

  log "[INFO] 检查 ${script_path} 是否已在运行..."
  local existing_pids
  existing_pids=$(pgrep -f "$script_path" || true)

  if [ -n "$existing_pids" ]; then
    log "[INFO] 检测到运行中的 ${script_path}，PIDs: $existing_pids，准备重启..."
    kill_by_pids "$existing_pids"
  else
    log "[INFO] 未发现运行中的 ${script_path}，直接启动。"
  fi

  log "[INFO] 启动后台服务: $script_path"
  mkdir -p "$(dirname "$log_path")"
  nohup "$VENV_PY" -u "$script_path" >> "$log_path" 2>&1 &
  local pid=$!

  log "[INFO] ${script_path} 已在后台启动，PID: $pid"
  echo "${name}_PID=$pid"
}

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
# 2. 一键启动/重启 workers（配置列表）
# 说明：
#   每一项格式：NAME|SCRIPT|LOG
#   NAME 用于输出变量：${NAME}_PID
# ============================
WORKERS=(
  "UPLOAD_WORKER|$REPO_PATH/upload_worker.py|$REPO_PATH/upload_worker.log"
  "MERGE_WORKER|$REPO_PATH/merge_worker.py|$REPO_PATH/merge_worker.log"
  "CHECKIN_SERVER|$REPO_PATH/checkin_server.py|$REPO_PATH/checkin_server.log"
  "REFRESH_TOKEN_SERVER|$REPO_PATH/refresh_token_server.py|$REPO_PATH/refresh_token_server.log"
  "FM_COMPLETE_WORKER|$REPO_PATH/fm_complete_worker.py|$REPO_PATH/fm_complete_worker.log"
)

for item in "${WORKERS[@]}"; do
  IFS='|' read -r name script_path log_path <<< "$item"
  restart_python_daemon "$name" "$script_path" "$log_path"
done

# ============================
# 3. 启动 Gunicorn（后台 + 清理旧进程）
# ============================
GUNICORN_LOG="$REPO_PATH/gunicorn.log"

log "[INFO] 清理旧的 gunicorn 进程..."
OLD_GUNICORN_PIDS=$(pgrep -f "gunicorn.*ZYT_AutoFM.*flask_server:app" || true)

if [ -n "$OLD_GUNICORN_PIDS" ]; then
  log "[INFO] 发现旧 gunicorn 进程: $OLD_GUNICORN_PIDS，准备终止"
  kill_by_pids "$OLD_GUNICORN_PIDS"
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
