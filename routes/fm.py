import json
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request

from apis.fm_api import FMApi
from db import UserInfo
from order_handler import OrderHandler
from oss_client import OSSClient
from utils.crypter import generate_random_coordinates
from utils.custom_raise import *

bp = Blueprint("fm", __name__)


# 完成工单
@bp.route("/api/fm/complete", methods=["POST"])
def complete_fm():
    payload = request.get_json(silent=True) or {}
    keyword = (payload.get("keyword", "") or "").strip()
    order_id = (payload.get("order_id", "") or "").strip()
    user_name = (payload.get("user_name", "") or "").strip()
    user_number = (payload.get("user_number", "") or "").strip()

    if not all([user_name, user_number]):
        return jsonify({
            "success": False,
            "error": "缺少参数",
            "code": "INVALID_PARAM"
        }), 400

    if all([keyword, order_id]):
        return jsonify({
            "success": False,
            "error": "keyword和order_id不能同时使用",
            "code": "ORDER_ALREADY_PROCESSED"
        }), 400

    if not keyword and not order_id:
        return jsonify({
            "success": False,
            "error": "缺少参数",
            "code": "INVALID_PARAM"
        }), 400

    fm = FMApi()
    oss = OSSClient(fm.session, fm.token)
    handler = OrderHandler(fm, oss)
    deal_data = fm.get_need_deal_list()
    records = deal_data.get("records", [])

    try:
        result = None
        if keyword:
            result = handler.complete_order_by_keyword(records, keyword, user_name, user_number)
        if order_id:
            result = handler.complete_order_by_id(records, order_id, user_name, user_number)
        if result:
            return jsonify({
                "success": True,
                "error": "",
                "data": result,
            })
        else:
            return jsonify({
                "success": False,
                "error": "未找到工单",
                "code": "ORDER_NOT_FOUND"
            }), 500
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


@bp.route("/api/fm/users", methods=["POST"])
def users_fm():
    try:
        users = list(UserInfo.select())
        items = [
            {
                "id": u.id,
                "name": u.name,
                "userNumber": u.user_number,
                "phone": u.phone,
                "device_model": u.device_model,
                "device_id": u.device_id,
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
@bp.route("/api/fm/pending_accept", methods=["POST"])
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
@bp.route("/api/fm/pending_process", methods=["POST"])
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
@bp.route("/api/fm/accept_task", methods=["POST"])
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
@bp.route("/api/fm/accept_muti_task", methods=["POST"])
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


# 打卡记录
@bp.route("/api/fm/checkin_record", methods=["POST"])
def checkin_record_fm():
    try:
        payload = request.get_json(silent=True) or {}
        user_number = payload.get("user_number", None)
        phone = payload.get("phone", "")

        if not all([user_number, phone]):
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        fm = FMApi(user_number=user_number)

        checkin_record = fm.checkin_record(phone)

        return jsonify({
            "success": True,
            "data": checkin_record
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 打卡
@bp.route("/api/fm/checkin", methods=["POST"])
def checkin_fm():
    try:
        payload = request.get_json(silent=True) or {}
        phone = payload.get("phone", "")
        device_model = payload.get("device_model", "")
        device_uuid = payload.get("device_uuid", "")

        if not all([phone, device_model, device_uuid]):
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        # 获取当前时间并格式化
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        geo_data = generate_random_coordinates()

        payload = {
            "attendances": [
                {
                    "altitude": 800.0,
                    "area": 1,
                    "bssid": "96:03:0c:22:02:ff",
                    "device_info": {
                        "app_type": "lebang",
                        "app_version": "6.36.0",
                        "cid": "0",
                        "imei": "",
                        "lac": "0",
                        "model": device_model,
                        "os_type": "android",
                        "os_version": "12",
                        "serial": "unknown",
                        "uuid": device_uuid
                    },
                    "faceCheckResult": 0,
                    "gd_latitude": geo_data['la'],
                    "gd_longitude": geo_data['lo'],
                    "inspectionTime": current_time,
                    "isBindPhone": True,
                    "isGCJ02": True,
                    "isLocalCache": True,
                    "latitude": geo_data['la'],
                    "longitude": geo_data['lo'],
                    "mobile": phone,
                    "moodAttendanceUser": True,
                    "project_code": "6055006346",
                    "project_name": "Q南宁中国锦园",
                    "send_time": current_time,
                    "source": "lebang",
                    "ssid": "Belkin_ff02220c0396",
                    "su_type": 0,
                    "success": True,
                    "takeImageType": 0,
                    "time": current_time,
                    "type": "-",
                    "verticalAccuracy": 0.0
                }
            ]
        }

        headers = {
            'User-Agent': "VKStaffAssistant-Android-6.36.0",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Content-Type': "application/json; charset=UTF-8",
            'X-Version': "6.36.0",
            'X-Platform': "Android",
            'X-API-Version': "20250813",
            'X-ORGC': "45010228",
            'X-Channel': "vanke",
            'X-isOld': "false",
            'X-Mobile': phone,
        }

        response = requests.post(
            url="https://api.vankeservice.com/api/app/staffs/saveSignedCard",
            data=json.dumps(payload),
            headers=headers
        )

        if response.status_code == 200:
            response_json = response.json()

            if response_json.get('code', -1) == 0:
                return jsonify({
                    "success": True,
                    "data": None
                })
            else:
                return jsonify({
                    "success": False,
                    "error": f"{response_json.get('error', '未知错误')}",
                }), 500

        else:
            return jsonify({
                "success": False,
                "error": "未知错误",
            }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"{str(e)}",
        }), 500
