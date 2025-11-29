from flask import Blueprint, jsonify, request

from apis.fm_api import FMApi
from order_handler import OrderHandler
from oss_client import OSSClient
from utils.custom_raise import *
from utils.notification import Notify

bp = Blueprint("fm", __name__)
notify = Notify()


@bp.route("/api/fm/complete", methods=["POST"])
def complete_fm():
    payload = request.get_json(silent=True) or {}
    keyword = (payload.get("keyword") or "").strip()
    user_name = (payload.get("user_name") or "").strip()

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
