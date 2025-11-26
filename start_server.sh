#!/usr/bin/env bash

# start_server.sh
# 用于部署 / 启动 ZYT_AutoFM：
# 1. 强制同步最新代码（丢弃本地修改）
# 2. 通过 db.py 初始化数据库
# 3. 启动 gunicorn

# ============================
# 基本路径配置（按需修改）
# ============================
REPO_PATH="/www/dk_project/dk_app/qinglong/QingLong/data/scripts/ZYT_AutoFM"
VENV_PY="/www/server/pyporject_evn/3820/bin/python3.8"
GUNICORN_BIN="/www/server/pyporject_evn/3820/bin/gunicorn"
GUNICORN_CONF="$REPO_PATH/gunicorn_conf.py"
APP_MODULE="flask_server:app"

cd "$REPO_PATH" || {
  echo "[ERROR] 无法切换到项目目录: $REPO_PATH"
  exit 1
}

# ============================
# 1. 强制同步最新代码（丢弃本地修改）
# ============================
echo "[INFO] 开始强制同步最新代码（丢弃本地修改）..."

GIT_CMD="
git reset --hard HEAD && \
git clean -fd && \
git fetch --all && \
git reset --hard origin/master
"

# 使用 timeout 防止 git 卡死，失败时给出提示但不直接退出
if ! timeout 30s bash -lc "$GIT_CMD"; then
  echo "[WARNING] Git 强制拉取失败或超时，将继续使用当前代码版本。"
else
  echo "[INFO] 代码已成功强制同步至 origin/master。"
fi

# ============================
# 2. 初始化数据库（执行 db.py）
#    显式使用 $REPO_PATH/db.py，避免路径混乱
# ============================
echo "[INFO] 执行 db.py 初始化数据库..."

if ! "$VENV_PY" "$REPO_PATH/db.py"; then
  echo "[ERROR] 数据库初始化失败（db.py 返回非 0），终止启动。"
  exit 1
fi

echo "[INFO] 数据库初始化完成。"

# ============================
# 3. 启动 Gunicorn
# ============================
echo "[INFO] 启动 Gunicorn 服务..."
echo "[INFO] 命令: $GUNICORN_BIN -c $GUNICORN_CONF $APP_MODULE"

# 使用 exec 替换当前 shell 进程，方便守护进程 / 宝塔管理
exec "$GUNICORN_BIN" -c "$GUNICORN_CONF" "$APP_MODULE"
