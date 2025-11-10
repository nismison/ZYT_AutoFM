import requests
from flask import Flask, request, Response

from config import BAICHUAN_BASE

app = Flask(__name__, static_folder=None)


@app.route('/', defaults={'subpath': ''}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@app.route('/<path:subpath>', methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def baichuan(subpath):
    # ---- 1. 请求路径重写 ----
    target_url = f"{BAICHUAN_BASE}/{subpath}" if subpath else f"{BAICHUAN_BASE}"

    # ---- 2. 处理请求头 ----
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
    cookies = request.cookies or {}
    baichuan_token = cookies.get("token", None)

    # ---- 3. 发起请求 ----
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            cookies=request.cookies,
            params=request.args,
            data=request.get_data(),
            allow_redirects=False,
            timeout=30,
            proxies={},
        )
    except requests.RequestException as e:
        return Response(f"Upstream request failed: {e}", status=502)

    # ---- 4. 输出响应 ----
    excluded = {'content-encoding', 'transfer-encoding', 'connection'}
    out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
    return Response(resp.content, resp.status_code, out_headers)


if __name__ == '__main__':
    app.run()
