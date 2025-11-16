from typing import Any, Dict

import yaml
from flask import Blueprint, jsonify

from utils.logger import log_line

bp = Blueprint("app_config", __name__)


def load_yaml_as_dict(path: str) -> Dict[str, Any]:
    """
    加载 YAML 配置文件并返回字典

    :param path: YAML 文件路径
    :returns: YAML 数据对应的 Python 字典
    :raises FileNotFoundError: 路径不存在
    :raises yaml.YAMLError: YAML 格式错误
    """
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


@bp.route("/api/app_config", methods=["GET"])
def app_config():
    """
    返回应用配置 (从 YAML 读取)
    """
    try:
        config = load_yaml_as_dict("app_config.yaml")
        log_line(f"[INFO] APP配置文件已加载")
        return jsonify({"success": True, "data": config})

    except FileNotFoundError:
        log_line("[ERROR] 配置文件未找到")
        return jsonify({
            "success": False,
            "error": "配置文件未找到",
            "code": "CONFIG_NOT_FOUND"
        }), 500

    except yaml.YAMLError as e:
        log_line(f"[ERROR] APP配置文件格式错误: {repr(e)}")
        return jsonify({
            "success": False,
            "error": f"配置文件格式错误: {str(e)}",
            "code": "CONFIG_PARSE_ERROR"
        }), 500

    except Exception as e:
        log_line(f"[ERROR] APP配置接口错误: {repr(e)}")
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500
