#!/usr/bin/env bash

# deploy_update.sh
# 1. 进入项目目录并 git pull 同步最新代码
# 2. 成功后调用 start_server.sh（此时已经是最新版本）

set -euo pipefail

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

REPO_PATH="/www/dk_project/dk_app/qinglong/QingLong/data/scripts/ZYT_AutoFM"
START_SCRIPT="$REPO_PATH/start_server.sh"

log "[INFO] 当前执行用户: $(whoami)"

cd "$REPO_PATH" || {
  log "[ERROR] 无法切换到项目目录: $REPO_PATH"
  exit 1
}

log "[INFO] 开始同步最新代码..."

GIT_CMD="git pull --ff-only"

# 使用 timeout 防止 git 卡死；失败则直接终止部署
if ! timeout 30s bash -lc "$GIT_CMD"; then
  log "[ERROR] Git 拉取失败或超时，终止部署。"
  exit 1
fi

log "[INFO] 代码已成功更新到最新。"

if [ ! -x "$START_SCRIPT" ]; then
  log "[WARN] $START_SCRIPT 不可执行，尝试添加执行权限..."
  chmod +x "$START_SCRIPT" || {
    log "[ERROR] 无法为 $START_SCRIPT 添加执行权限，终止部署。"
    exit 1
  }
fi

log "[INFO] 调用最新版本的 start_server.sh 启动服务..."
exec "$START_SCRIPT"
