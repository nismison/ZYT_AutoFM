import json

import requests
from flask import Blueprint, request, Response
from peewee import DoesNotExist

from apis.ql_api import QLApi
from config import TARGET_BASE
from db import UserInfo
from utils.logger import log_line
from utils.notification import Notify

bp = Blueprint("proxy", __name__)


def upsert_user_info(user_number, name, phone, device_model, token):
    """
    按 user_number 执行 upsert：
    - 若存在：更新 token/name/phone/device_model
    - 若不存在：新建记录
    """
    try:
        user = UserInfo.get(UserInfo.user_number == user_number)
        # 存在 → 更新
        user.name = name
        user.phone = phone
        user.device_model = device_model
        user.token = token
        user.save()  # 只更新变动字段（peewee 自动对比）
        log_line(f"[UserInfo] 更新用户: {user_number}")
    except DoesNotExist:
        # 不存在 → 创建
        UserInfo.create(
            user_number=user_number,
            name=name,
            phone=phone,
            device_model=device_model,
            token=token,
        )
        log_line(f"[UserInfo] 创建新用户: {user_number}")
    except Exception as e:
        log_line(f"[UserInfo] upsert 失败: {repr(e)}")


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
        if original_path == "heimdall/api/oauth/access_token":
            try:
                data = resp.json() or {}
                user_number = str(data.get('staffId'))
                result = data.get('result') or {}
                access_token = result.get('access_token')
            except Exception:
                access_token = None
                user_number = None
            if access_token and user_number:
                try:
                    rows = (
                        UserInfo
                        .update(token=access_token)
                        .where(UserInfo.user_number == user_number)
                        .execute()
                    )
                    if rows == 0:
                        log_line(f"[UserInfo] 未找到 user_number={user_number} 的用户, 无法更新 token")
                    else:
                        log_line(f"[UserInfo] 更新 token 成功, user_number={user_number}")
                        Notify().send(f"Token更新成功: ...{access_token[-10:] if access_token else ''}")
                except Exception as e:
                    log_line(f"[UserInfo] 更新 token 失败, user_number={user_number}, error={repr(e)}")

        if original_path == "hulk/thor/api/report":
            try:
                token = request.headers.get("Authorization").split(" ")[1]
                data = request.get_data(as_text=True)
                data_json = json.loads(data)

                reportList = data_json.get("reportList", [])
                event_description = reportList[0].get("eventDescription")

                if event_description == "启动APP":
                    name = reportList[0].get("employeeName")
                    phone = reportList[0].get("phoneNo")
                    device_model = reportList[0].get("deviceModel")
                    user_number = str(reportList[0].get("staffId"))

                    log_line(f"{name} {phone} {device_model} {user_number}")

                    # 执行数据库 upsert
                    upsert_user_info(
                        user_number=user_number,
                        name=name,
                        phone=phone,
                        device_model=device_model,
                        token=token,
                    )

            except Exception as e:
                log_line(f"解析上报数据失败: {repr(e)}")

    return Response(resp.content, resp.status_code, out_headers)
