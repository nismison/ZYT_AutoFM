import requests
from flask import Blueprint, request, Response
from peewee import DoesNotExist

from auto_refresh_token import force_update_tokens_by_user_number
from config import TARGET_BASE
from db import UserInfo
from utils.bind_info import fetch_bind_info, fetch_me_info
from utils.logger import log_line
from utils.notification import Notify

bp = Blueprint("proxy", __name__)


def upsert_user_info(token, user_number, name, phone, device_model, device_id, token_expires):
    """
    按 user_number 执行 upsert：
    - 若存在：更新 token/name/phone/device_model
    - 若不存在：新建记录
    """
    try:
        user = UserInfo.get(UserInfo.user_number == user_number)
        # 存在 → 更新
        user.token = token
        user.name = name
        user.phone = phone
        user.device_model = device_model
        user.device_id = device_id
        user.token_expires = token_expires
        user.save()  # 只更新变动字段（peewee 自动对比）
        log_line(f"[INFO] [UserInfo] 更新用户: {user_number}")
    except DoesNotExist:
        # 不存在 → 创建
        UserInfo.create(
            token=token,
            user_number=user_number,
            name=name,
            phone=phone,
            device_model=device_model,
            device_id=device_id,
            token_expires=token_expires,
        )
        log_line(f"[INFO] [UserInfo] 创建新用户: {user_number}")
    except Exception as e:
        log_line(f"[ERROR] [UserInfo] upsert 失败: {repr(e)}")


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
                token_expires = result.get('expires')
            except Exception:
                access_token = None
                user_number = None
                token_expires = 0

            if access_token and user_number:
                try:
                    # 获取设备绑定信息
                    bind_info = fetch_bind_info(access_token)
                    phone = bind_info.get("loginMobile")
                    device_model = bind_info.get("deviceModel")
                    device_id = bind_info.get("deviceID")

                    # 获取用户名
                    name = fetch_me_info(access_token)

                    upsert_user_info(
                        token=access_token,
                        user_number=user_number,
                        name=name,
                        phone=phone,
                        device_model=device_model,
                        device_id=device_id,
                        token_expires=token_expires,
                    )

                    # 强制刷新 token
                    force_update_tokens_by_user_number(user_number)

                    log_line(
                        f"[INFO] [UserInfo] 用户信息 更新成功, {user_number} {name} {phone} {device_model} {device_id}")
                    Notify().send(f"[{name}] Token更新成功: ...{access_token[-10:] if access_token else ''}")

                except Exception as e:
                    log_line(f"[INFO] [UserInfo] 更新 token 失败, user_number={user_number}, error={repr(e)}")

    return Response(resp.content, resp.status_code, out_headers)
