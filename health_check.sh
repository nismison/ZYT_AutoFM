#!/usr/bin/env bash
# health_check.sh
# 检查 upload_worker、merge_worker、checkin_server、gunicorn

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "[INFO] 开始健康检查"

check_single_process() {
  local name="$1"
  local pid
  pid=$(pgrep -f "$name" || true)
  count=$(echo "$pid" | wc -w)
  if [ "$count" -eq 1 ]; then
    log "[OK] $name 正常运行，PID=$pid"
  elif [ "$count" -eq 0 ]; then
    log "[FAIL] $name 未运行"
  else
    log "[FAIL] $name 存在多进程 ($count 个)，PIDs=$pid"
  fi
}

# 检查 Worker
check_single_process "upload_worker.py"
check_single_process "merge_worker.py"
check_single_process "checkin_server.py"

# 检查 Gunicorn
GUNICORN_PIDS=$(pgrep -f "gunicorn.*ZYT_AutoFM.*flask_server:app" || true)

if [ -z "$GUNICORN_PIDS" ]; then
  log "[FAIL] gunicorn 未运行"
else
  MASTER_PID=$(echo "$GUNICORN_PIDS" | head -1)
  WORKER_PIDS=$(echo "$GUNICORN_PIDS" | tail -n +2)
  log "[OK] gunicorn master 正常，PID=$MASTER_PID"
  if [ -n "$WORKER_PIDS" ]; then
    log "[OK] gunicorn worker 数量=$(echo "$WORKER_PIDS" | wc -w)，PIDs=$WORKER_PIDS"
  else
    log "[WARN] gunicorn 没有检测到 worker"
  fi
fi

# 检查总结果
FAIL_COUNT=$((
  $(pgrep -f "upload_worker.py" | wc -l) != 1 ? 1 : 0 +
  $(pgrep -f "merge_worker.py" | wc -l) != 1 ? 1 : 0 +
  $(pgrep -f "checkin_server.py" | wc -l) != 1 ? 1 : 0 +
  [ -z "$GUNICORN_PIDS" ] ? 1 : 0
))
if [ "$FAIL_COUNT" -eq 0 ]; then
  log "[INFO] 所有服务健康"
else
  log "[ERROR] 存在异常服务"
fi
