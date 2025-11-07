import requests
from flask import Blueprint, request, Response
from config import TARGET_BASE
from apis.ql_api import QLApi
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

    # 业务场景：登录成功时写入青龙环境变量
    if original_path == "heimdall/api/oauth/access_token" and resp.status_code == 200:
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

    return Response(resp.content, resp.status_code, out_headers)