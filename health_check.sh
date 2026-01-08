#!/usr/bin/env bash
# health_check.sh
# 严格健康检查（工程级）
#
# upload_worker / merge_worker / checkin_server:
#   - 有且仅有 1 个进程
#
# gunicorn:
#   - master = 1
#   - worker >= 1
#
# exit code:
#   0 = 全部正常
#   1 = 任一异常

set -euo pipefail

REPO_PATH="/root/ZYT_AutoFM"

UPLOAD_WORKER="$REPO_PATH/upload_worker.py"
MERGE_WORKER="$REPO_PATH/merge_worker.py"
CHECKIN_SERVER="$REPO_PATH/checkin_server.py"
GUNICORN_BIN="/www/server/pyporject_evn/3820/bin/gunicorn"

EXIT_CODE=0

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

fail() {
  log "[FAIL] $*"
  EXIT_CODE=1
}

ok() {
  log "[OK] $*"
}

# ============================
# 单实例进程检查
# ============================
check_single_process() {
  local name="$1"
  local pattern="$2"

  local pids
  pids="$(pgrep -f "$pattern" || true)"
  local count
  count="$(echo "$pids" | sed '/^\s*$/d' | wc -l)"

  if [ "$count" -eq 1 ]; then
    ok "$name 正常运行，PID=$pids"
  elif [ "$count" -eq 0 ]; then
    fail "$name 未运行"
  else
    fail "$name 进程数异常($count)，PIDs=$pids"
  fi
}

# ============================
# Gunicorn 检查（master / worker）
# ============================
check_gunicorn() {
  local pids
  pids="$(pgrep -f "$GUNICORN_BIN" || true)"

  if [ -z "$pids" ]; then
    fail "gunicorn 未运行"
    return
  fi

  local masters=()
  local workers=()

  for pid in $pids; do
    local ppid
    ppid="$(ps -o ppid= -p "$pid" | tr -d ' ')"

    if echo "$pids" | grep -qw "$ppid"; then
      workers+=("$pid")
    else
      masters+=("$pid")
    fi
  done

  if [ "${#masters[@]}" -ne 1 ]; then
    fail "gunicorn master 数异常(${#masters[@]})，PIDs=${masters[*]:-none}"
  else
    ok "gunicorn master 正常，PID=${masters[0]}"
  fi

  if [ "${#workers[@]}" -lt 1 ]; then
    fail "gunicorn worker 不存在"
  else
    ok "gunicorn worker 数量=${#workers[@]}，PIDs=${workers[*]}"
  fi
}

# ============================
# 执行检查
# ============================
log "[INFO] 开始健康检查"

check_single_process "upload_worker" "$UPLOAD_WORKER"
check_single_process "merge_worker" "$MERGE_WORKER"
check_single_process "checkin_server" "$CHECKIN_SERVER"
check_gunicorn

if [ "$EXIT_CODE" -eq 0 ]; then
  log "[INFO] 所有服务健康"
else
  log "[ERROR] 存在异常服务"
fi

exit "$EXIT_CODE"
