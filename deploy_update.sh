#!/usr/bin/env bash

# deploy_update.sh
# 1. 进入项目目录并 git pull 同步最新代码
# 2. 成功后调用最新版本的 start_server.sh
#
# 注意：
# - 不做任何启动逻辑，只负责更新 + 调用
# - start_server.sh 必须已经是可执行文件（+x）

set -euo pipefail

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

REPO_PATH="/root/ZYT_AutoFM"
START_SCRIPT="$REPO_PATH/start_server.sh"

log "[INFO] 当前执行用户: $(whoami)"

cd "$REPO_PATH" || {
  log "[ERROR] 无法切换到项目目录: $REPO_PATH"
  exit 1
}

log "[INFO] 开始同步最新代码..."

GIT_CMD="git checkout . && git pull --ff-only"

# 防止 git 卡死；失败直接终止部署
if ! timeout 30s bash -lc "$GIT_CMD"; then
  log "[ERROR] Git 拉取失败或超时，终止部署。"
  exit 1
fi

log "[INFO] 代码已成功更新到最新。"

# 不再尝试 chmod，发现不可执行直接报错提示你用 root 修
if [ ! -x "$START_SCRIPT" ]; then
  log "[ERROR] $START_SCRIPT 不可执行，请在服务器上用 root 执行: chmod +x $START_SCRIPT"
  exit 1
fi

log "[INFO] 调用最新版本的 start_server.sh 启动服务..."
exec "$START_SCRIPT"
