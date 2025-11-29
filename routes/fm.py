from flask import Blueprint, jsonify, request

from apis.fm_api import FMApi
from db import UserInfo
from order_handler import OrderHandler
from oss_client import OSSClient
from utils.custom_raise import *
from utils.notification import Notify

bp = Blueprint("fm", __name__)
notify = Notify()


@bp.route("/api/fm/complete", methods=["POST"])
def complete_fm():
    payload = request.get_json(silent=True) or {}
    keyword = payload.get("keyword", "").strip()
    user_name = payload.get("user_name", "").strip()

    if not all([keyword, user_name]):
        return jsonify({
            "success": False,
            "error": "缺少关键字 keyword 或姓名 user_name",
            "code": "INVALID_PARAM"
        }), 400

    fm = FMApi()
    oss = OSSClient(fm.session, fm.token)
    handler = OrderHandler(fm, oss)
    deal_data = fm.get_need_deal_list()
    records = deal_data.get("records", [])

    try:
        result = handler.complete_order_by_keyword(records, keyword, user_name)
        return jsonify({
            "success": True,
            "error": "",
            "data": result,
        })
    except OrderNotFoundError as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    except UserNotFoundError as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    except (RuleNotFoundError, ImageUploadError, PartialUploadError) as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@bp.route("/api/fm/users", methods=["GET"])
def users_fm():
    try:
        users = list(UserInfo.select())
        items = [
            {
                "id": u.id,
                "name": u.name,
                "userNumber": u.user_number,
            }
            for u in users
        ]

        return jsonify({
            "success": True,
            "data": {
                "items": items
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 获取待接单工单
@bp.route("/api/fm/pending_accept", methods=["GET"])
def pending_accept_fm():
    try:
        payload = request.get_json(silent=True) or {}
        user_number = payload.get("user_number", None)
        if user_number is None:
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        fm = FMApi(user_number=user_number)
        records = fm.get_task_list()
        return jsonify({
            "success": True,
            "data": {
                "items": records.get("records", [])
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 获取待处理工单
@bp.route("/api/fm/pending_process", methods=["GET"])
def pending_process_fm():
    try:
        payload = request.get_json(silent=True) or {}
        user_number = payload.get("user_number", None)
        if user_number is None:
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        fm = FMApi(user_number=user_number)
        records = fm.get_need_deal_list()
        return jsonify({
            "success": True,
            "data": {
                "items": records.get("records", [])
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 接单
@bp.route("/api/fm/accept_task", methods=["GET"])
def accept_task_fm():
    try:
        payload = request.get_json(silent=True) or {}
        user_number = payload.get("user_number", None)
        order_id = payload.get("order_id", None)
        if not all([user_number, order_id]):
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        fm = FMApi(user_number=user_number)
        data = fm.accept_task(order_id)
        return jsonify({
            "success": True,
            "data": data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 批量接单
@bp.route("/api/fm/accept_muti_task", methods=["GET"])
def accept_muti_task_fm():
    try:
        payload = request.get_json(silent=True) or {}
        user_number = payload.get("user_number", None)
        order_ids = payload.get("order_ids", [])
        if not all([user_number, order_ids]):
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        fm = FMApi(user_number=user_number)

        for order_id in order_ids:
            fm.accept_task(order_id)

        return jsonify({
            "success": True,
            "data": {}
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500
