#!/usr/bin/env bash

# health_check.sh
# 严格健康检查：
# - upload_worker.py
# - merge_worker.py
# - checkin_server.py
# - gunicorn
#
# 规则：
#   有且仅有 1 个进程 => OK
#   0 个或 >1 个 => FAIL
#
# 退出码：
#   0 = 全部健康
#   1 = 任一服务异常

set -euo pipefail

REPO_PATH="/root/ZYT_AutoFM"

UPLOAD_WORKER="$REPO_PATH/upload_worker.py"
MERGE_WORKER="$REPO_PATH/merge_worker.py"
CHECKIN_SERVER="$REPO_PATH/checkin_server.py"
GUNICORN_KEYWORD="gunicorn"

EXIT_CODE=0

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

check_single_process() {
  local name="$1"
  local pattern="$2"

  # pgrep -f：按完整命令行匹配
  local pids
  pids="$(pgrep -f "$pattern" || true)"
  local count
  count="$(echo "$pids" | sed '/^\s*$/d' | wc -l)"

  if [ "$count" -eq 1 ]; then
    log "[OK] $name 正常运行，PID: $pids"
  elif [ "$count" -eq 0 ]; then
    log "[FAIL] $name 未运行"
    EXIT_CODE=1
  else
    log "[FAIL] $name 进程数异常（$count 个），PIDs: $pids"
    EXIT_CODE=1
  fi
}

log "[INFO] 开始服务健康检查..."

# ============================
# upload_worker
# ============================
check_single_process "upload_worker" "$UPLOAD_WORKER"

# ============================
# merge_worker
# ============================
check_single_process "merge_worker" "$MERGE_WORKER"

# ============================
# checkin_server
# ============================
check_single_process "checkin_server" "$CHECKIN_SERVER"

# ============================
# gunicorn
# 说明：
# - 不使用 pidfile
# - 不假设 worker 数
# - 只检查 master 进程
# ============================
check_single_process "gunicorn(master)" "$GUNICORN_KEYWORD: master"

# 兜底（某些 gunicorn 启动参数不显示 master）
if [ "$EXIT_CODE" -eq 0 ]; then
  :
else
  # 如果 master 匹配失败，再用宽松规则检测一次
  GUNICORN_PIDS="$(pgrep -f "$GUNICORN_KEYWORD" || true)"
  GUNICORN_COUNT="$(echo "$GUNICORN_PIDS" | sed '/^\s*$/d' | wc -l)"

  if [ "$GUNICORN_COUNT" -eq 1 ]; then
    log "[WARN] gunicorn 未匹配到 master 标识，但仅有一个进程存在，PID: $GUNICORN_PIDS"
    EXIT_CODE=0
  fi
fi

# ============================
# 结果
# ============================
if [ "$EXIT_CODE" -eq 0 ]; then
  log "[INFO] 健康检查通过：所有服务状态正常"
else
  log "[ERROR] 健康检查失败：存在异常服务"
fi

exit "$EXIT_CODE"
