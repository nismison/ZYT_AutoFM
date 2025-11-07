from flask import Blueprint, jsonify, request
from utils.notification import Notify

bp = Blueprint("notify", __name__)
notify = Notify()


@bp.route("/send_notify", methods=["POST"])
def send_notify():
    data = request.get_json(silent=True) or {}
    content = data.get("content")
    if not content:
        return jsonify({"error": "缺少content"}), 400
    notify.send(content)
    return jsonify({"success": True})