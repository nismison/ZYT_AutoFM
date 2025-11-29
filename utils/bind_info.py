import requests


def auth_headers(token: str) -> dict:
    """构造带 Authorization 的通用请求头"""
    return {"authorization": f"Bearer {token}"}


def get_session_id(session: requests.Session, token: str) -> str:
    """
    Step 1: 访问 employee-bind-phone，建立会话并拿到 SESSION ID
    """
    url = f"https://rm.vankeservice.com/home-app/employee-bind-phone"
    resp = session.get(url, headers=auth_headers(token))
    resp.raise_for_status()

    session_id = resp.cookies.get("SESSION")
    if not session_id:
        # 兜底：有些情况下只从 Set-Cookie 拿
        set_cookie = resp.headers.get("Set-Cookie", "")
        for part in set_cookie.split(";"):
            if part.strip().startswith("SESSION="):
                session_id = part.strip().split("=", 1)[1]
                break

    if not session_id:
        raise RuntimeError("无法获取 SESSION ID")

    return session_id


def get_jump_location(session: requests.Session, token: str, session_id: str) -> str:
    """
    Step 2: 请求 /login/app/employee/same/jump，拿到第一次 Location 跳转地址
    """
    url = f"https://rm.vankeservice.com/login/app/employee/same/jump?jumpUrl=/toller/"
    headers = auth_headers(token)
    headers["Cookie"] = f"SESSION={session_id}"

    resp = session.get(url, headers=headers, allow_redirects=False)
    location = resp.headers.get("Location")
    if not location:
        raise RuntimeError("Step 2: 响应中缺少 Location 头")

    return location


def follow_redirect_without_cookie(session: requests.Session, token: str, url: str) -> str:
    """
    Step 3: 跟随第一次 Location（不带 Cookie），拿到新的 Location
    """
    resp = session.get(url, headers=auth_headers(token), allow_redirects=False)
    location = resp.headers.get("Location")
    if not location:
        raise RuntimeError("Step 3: 响应中缺少 Location 头")
    return location


def follow_redirect_with_cookie(session: requests.Session, token: str, session_id: str, url: str) -> str:
    """
    Step 4: 再次跟随 Location（带 Cookie），拿到最终包含参数的 URL
    """
    headers = auth_headers(token)
    headers["Cookie"] = f"SESSION={session_id}"

    resp = session.get(url, headers=headers, allow_redirects=False)
    location = resp.headers.get("Location")
    if not location:
        raise RuntimeError("Step 4: 响应中缺少 Location 头")
    return location


# 之前给你的 extract_query_params，可直接复用
from urllib.parse import urlparse, parse_qs


def extract_query_params(url: str) -> dict:
    """
    从 URL 中提取所有 query 参数，返回 {key: value} 字典。
    兼容：
      - https://xxx/path?a=1&b=2
      - https://xxx/path#/sub?a=1&b=2
      - https://xxx/path#a=1&b=2
    """
    parsed = urlparse(url)
    query_str = parsed.query

    # 如果标准 query 为空，尝试从 fragment 中解析
    if not query_str and parsed.fragment:
        frag = parsed.fragment
        if "?" in frag:
            query_str = frag.split("?", 1)[1]
        elif "=" in frag:
            query_str = frag

    if not query_str:
        return {}

    raw = parse_qs(query_str, keep_blank_values=True)
    return {k: v[0] if v else "" for k, v in raw.items()}


# ====================== 主流程 ======================
def fetch_bind_info(token: str):
    TOKEN = token

    session = requests.Session()

    # Step 1: 获取 SESSION ID
    session_id = get_session_id(session, TOKEN)

    # Step 2: 获取第一次 Location（跳转到 toller 相关入口）
    first_location = get_jump_location(session, TOKEN, session_id)

    # Step 3: 不带 Cookie 跟随跳转，拿到第二次 Location
    second_location = follow_redirect_without_cookie(session, TOKEN, first_location)

    # Step 4: 带 Cookie 再跟一次跳转，拿到最终 URL（包含 loginMobile、token、deviceID 等）
    final_url = follow_redirect_with_cookie(session, TOKEN, session_id, second_location)

    # 提取最终 URL 中的参数
    params = extract_query_params(final_url)
    return params

def fetch_me_info(token: str):
    url = "https://api.zytsy.icu/redirect/galaxy/api/app/staffs/me/detail"
    headers = {
        'authorization': f"Bearer {token}",
    }
    response = requests.get(url, headers=headers)
    name = response.json().get("result", {}).get("fullname", "")
    return name


if __name__ == '__main__':
    bind_info = fetch_bind_info("eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJBQ0NFU1NfVE9LRU4iLCJjbGllbnRJZCI6IjVlOTZlYWMwNjE1MWQwY2UyZGQ5NTU0ZDdlZTE2N2NlIiwic2NvcGUiOiJhbGwgci1zdGFmZiIsInRva2VuIjoiMjQwOTg0MCIsImlhdCI6MTc2NDM3OTI1MiwiZXhwIjoxNzY0OTg0MDUyfQ.SKABoS8bcEChk8IHAB5ZF9w3yl4_y3887bKY6Wq1-Qs")
    print(bind_info)
