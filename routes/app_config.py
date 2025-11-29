from typing import Any, Dict

import yaml
from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from db import UserInfo
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


# ---------------------------------------------------------
#  新增接口：用户管理
#  1) POST /api/users  新增用户
#  2) GET  /api/users  查询全部用户
# ---------------------------------------------------------

@bp.route("/api/users", methods=["POST"])
def create_user():
    """
    新增用户：
    请求体 JSON:
    {
      "name": "张三",
      "userNumber": "1234567"
    }
    """
    try:
        payload = request.get_json(silent=True) or {}
        name = (payload.get("name") or "").strip()
        user_number = str(payload.get("userNumber") or "").strip()

        if not name:
            return jsonify({
                "success": False,
                "error": "缺少姓名 name",
                "code": "INVALID_PARAM"
            }), 400

        # 要求 7 位数字
        if len(user_number) != 7 or not user_number.isdigit():
            return jsonify({
                "success": False,
                "error": "userNumber 必须为 7 位数字",
                "code": "INVALID_USER_NUMBER"
            }), 400

        user = UserInfo.create(
            name=name,
            user_number=user_number,
        )

        return jsonify({
            "success": True,
            "data": {
                "id": user.id,
                "name": user.name,
                "userNumber": user.user_number,
            }
        })

    except IntegrityError:
        # user_number 唯一约束冲突
        log_line(f"[WARN] 尝试创建重复 userNumber: {request.get_json(silent=True)}")
        return jsonify({
            "success": False,
            "error": "userNumber 已存在",
            "code": "USER_NUMBER_EXISTS"
        }), 400

    except Exception as e:
        log_line(f"[ERROR] 新增用户接口错误: {repr(e)}")
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500
