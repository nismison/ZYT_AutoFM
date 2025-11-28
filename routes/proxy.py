import json

import requests
from flask import Blueprint, request, Response

from apis.ql_api import QLApi
from config import TARGET_BASE
from utils.logger import log_line
from utils.notification import Notify

bp = Blueprint("proxy", __name__)


@bp.route('/redirect', defaults={'subpath': ''}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@bp.route('/redirect/<path:subpath>', methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy(subpath):
    # 去掉 "/redirect" 前缀，保留原始相对路径
    original_path = request.path[len('/redirect'):].lstrip('/')
    target_url = f"{TARGET_BASE}/{original_path}"

    # 复制请求头，移除 host
    headers = {k: v for k, v in request.headers if k.lower() != 'host'}

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=30,
            proxies={},
        )
    except requests.RequestException as e:
        return Response(f"Upstream request failed: {e}", status=502)

    # 过滤 hop-by-hop 头
    excluded = {'content-encoding', 'transfer-encoding', 'connection'}
    out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}

    if resp.status_code == 200:
        # 业务场景：登录成功时写入青龙环境变量
        if original_path == "heimdall/api/oauth/access_token":
            try:
                data = resp.json() or {}
                result = data.get('result') or {}
                access_token = result.get('access_token')
            except Exception:
                access_token = None
            if access_token:
                ql = QLApi()
                ok = ql.update_env("ZYT_TOKEN", access_token)
                Notify().send(f"Token更新{'成功' if ok else '失败'}: ...{access_token[-10:] if access_token else ''}")

        if original_path == "hulk/position/api/location/upload":
            log_line(json.dumps(request.headers))
            data = request.get_data(as_text=True)
            data_json = json.loads(data)
            name = data_json.get("employeeName")
            phone = data_json.get("phoneNo")
            user_number = data_json.get("staffId")
            log_line(name)
            log_line(phone)
            log_line(user_number)

            facilityPositionExtend = data_json.get("facilityPositionExtend", {})
            uuid = facilityPositionExtend.get("deviceId")
            device_model = facilityPositionExtend.get("deviceModel")
            log_line(uuid)
            log_line(device_model)

        # if original_path == "galaxy/api/app/staff/favorite/module":
        #     try:
        #         data = resp.json() or {}
        #         for item in data["result"] or []:
        #             if "百川工单" in item["name"]:
        #                 item["action_id"] = f"{BAICHUAN_PROXY_URL}/api/client/auth/index?uri=/"
        #                 item["action_url"] = f"{BAICHUAN_PROXY_URL}/api/client/auth/index?uri=/"
        #         return jsonify(data), resp.status_code, out_headers
        #     except Exception:
        #         pass

    return Response(resp.content, resp.status_code, out_headers)