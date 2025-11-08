import os
import json
from flask import Blueprint, jsonify, send_from_directory

bp = Blueprint("update", __name__)

APK_DIR = "apks"
CONFIG_FILE = "update_config.json"


def load_config():
    """读取本地配置文件"""
    default = {
        "silent": 0,
        "force": 1,
        "net_check": 0,
        "note": ""
    }
    if not os.path.exists(CONFIG_FILE):
        return default
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            default.update(data)
    except Exception:
        pass
    return default


def parse_version(filename: str):
    """解析文件名中的版本号"""
    name, ext = os.path.splitext(filename)
    parts = name.split('.')
    try:
        return tuple(map(int, parts)), ext.lstrip('.')
    except ValueError:
        return None, None


def find_latest_file():
    """找到版本号最大的文件"""
    files = [f for f in os.listdir(APK_DIR) if f.endswith(('.apk', '.wgt'))]
    latest = None
    latest_ver = (-1, -1, -1)

    for f in files:
        version_tuple, _ = parse_version(f)
        if not version_tuple:
            continue
        if version_tuple > latest_ver:
            latest_ver = version_tuple
            latest = f

    if latest:
        version_str = '.'.join(map(str, latest_ver))
        return {
            "version": version_str,
            "filename": latest
        }
    return None


@bp.route("/api/check_update", methods=["GET"])
def check_update():
    """返回最大版本号的文件信息"""
    config = load_config()
    latest = find_latest_file()
    if not latest:
        return jsonify({
            "version": "0.0.0",
            "now_url": "",
            **config
        })

    return jsonify({
        "version": latest["version"],
        "now_url": f"/api/download/{latest['filename']}",
        **config
    })


@bp.route("/api/download/<path:filename>")
def download_file(filename):
    """文件直链接口"""
    return send_from_directory(APK_DIR, filename, as_attachment=False)
