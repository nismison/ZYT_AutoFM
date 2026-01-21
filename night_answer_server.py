import os
import time
import requests
from urllib.parse import urlparse, parse_qs, urljoin
from datetime import datetime
from config import TZ
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from db import UserInfo
from utils.logger import log_line

REDIRECT_CODES = (301, 302, 303, 307, 308)
RETRY_HTTP = {429, 500, 502, 503, 504}


def normalize_auth(token: str, mode: str) -> str:
    """
    mode:
      - "raw":    Authorization: <token>
      - "bearer": Authorization: Bearer <token>   (如果已带 Bearer 就不重复加)
    """
    t = (token or "").strip()
    if not t:
        raise ValueError("empty token")
    if mode == "raw":
        return t
    if t.lower().startswith("bearer "):
        return t
    return f"Bearer {t}"


def safe_json(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except ValueError as e:
        text = (resp.text or "")[:300]
        raise RuntimeError(f"响应不是合法 JSON: http={resp.status_code}, text={text}") from e


def request_with_retry(make_request, *, retries: int = 2, backoff: float = 0.6):
    last_err = None
    for i in range(retries + 1):
        try:
            resp = make_request()
            if resp.status_code in RETRY_HTTP and i < retries:
                time.sleep(backoff * (2 ** i))
                continue
            return resp
        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = e
            if i >= retries:
                break
            time.sleep(backoff * (2 ** i))
    raise RuntimeError("网络请求多次失败") from last_err


def get_location(resp: requests.Response, base_url: str) -> str:
    loc = resp.headers.get("Location")
    if not loc:
        raise RuntimeError(f"期望重定向但没有 Location: status={resp.status_code}, url={base_url}")
    return urljoin(base_url, loc)


def parse_access_token_from_fragment(url: str) -> str:
    u = urlparse(url)
    _, _, q = u.fragment.partition("?")
    params = parse_qs(q)
    token = params.get("accessToken", [None])[0]
    if not token:
        raise RuntimeError(f"final url fragment 里没找到 accessToken: {url}")
    return token


def resolve_access_token(session: requests.Session, start_url: str, login_bearer: str, timeout: int = 10) -> str:
    session.headers.update({"Authorization": normalize_auth(login_bearer, "bearer")})

    r1 = request_with_retry(lambda: session.get(start_url, allow_redirects=False, timeout=timeout))
    if r1.status_code not in REDIRECT_CODES:
        r1.raise_for_status()
        raise RuntimeError(f"第一跳不是重定向: {r1.status_code}")
    u2 = get_location(r1, start_url)

    r2 = request_with_retry(lambda: session.get(u2, allow_redirects=False, timeout=timeout))
    if r2.status_code not in REDIRECT_CODES:
        r2.raise_for_status()
        raise RuntimeError(f"第二跳不是重定向: {r2.status_code}")
    u3 = get_location(r2, u2)

    r3 = request_with_retry(lambda: session.get(u3, allow_redirects=False, timeout=timeout))
    if r3.status_code not in REDIRECT_CODES:
        r3.raise_for_status()
        raise RuntimeError(f"第三跳不是重定向: {r3.status_code}")
    u4 = get_location(r3, u3)

    return parse_access_token_from_fragment(u4)


def api_get_json(session: requests.Session, url: str, *, access_token: str, timeout: int = 10,
                 params: dict | None = None) -> dict:
    """
    有些服务端要求 Authorization 直接放 token，有些要求 Bearer token
    这里做一个兼容：先用 raw，遇到 401 再用 bearer 重试一次
    """

    def do(mode: str):
        headers = {"Authorization": normalize_auth(access_token, mode)}
        resp = request_with_retry(lambda: session.get(url, params=params, headers=headers, timeout=timeout))
        return resp

    resp = do("raw")
    if resp.status_code == 401:
        resp = do("bearer")

    resp.raise_for_status()
    data = safe_json(resp)
    if isinstance(data, dict) and data.get("code") not in (200, 0, None):
        raise RuntimeError(f"业务失败: code={data.get('code')}, msg={data.get('message')}")
    return data


def api_put_json(session: requests.Session, url: str, *, access_token: str, timeout: int = 10,
                 params: dict | None = None) -> dict:
    def do(mode: str):
        headers = {"Authorization": normalize_auth(access_token, mode)}
        resp = request_with_retry(lambda: session.put(url, params=params, headers=headers, timeout=timeout))
        return resp

    resp = do("raw")
    if resp.status_code == 401:
        resp = do("bearer")

    resp.raise_for_status()
    data = safe_json(resp)
    if isinstance(data, dict) and data.get("code") not in (200, 0, None):
        raise RuntimeError(f"业务失败: code={data.get('code')}, msg={data.get('message')}")
    return data


def fetch_doing_list(session: requests.Session, access_token: str, timeout: int = 10) -> list[dict]:
    url = "https://rm.vankeservice.com/api/easycheck/night_school/page"
    data = api_get_json(
        session, url,
        access_token=access_token,
        timeout=timeout,
        params={"page": 1, "per_page": 30, "status": "doing"},
    )
    return data.get("result") or []


def fetch_question_by_id(session: requests.Session, access_token: str, qid: int, timeout: int = 10) -> dict:
    url = f"https://rm.vankeservice.com/api/easycheck/night_school/getById/{qid}"
    data = api_get_json(session, url, access_token=access_token, timeout=timeout)
    return data.get("result") or {}


def submit_answer(session: requests.Session, access_token: str, qid: int, timeout: int = 10) -> dict:
    url = f"https://rm.vankeservice.com/api/easycheck/night_school/{qid}"
    data = api_put_json(
        session, url,
        access_token=access_token,
        timeout=timeout,
        params={"answer": 0},
    )
    return data


def task():
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] run task")

    start_url = "https://rm.vankeservice.com/api/easycheck/web/index?wkwebview=true&rurl=/nightAnswer"
    timeout = 10

    users = UserInfo.select().where(UserInfo.token.is_null(False) and UserInfo.token_expires > int(time.time()))

    total = users.count()
    print(f"{'=' * 25} 夜答开始，共 {total} 个用户 {'=' * 25}")

    for user in users:
        print(f"\n------ 处理用户 {user.user_number}（{user.name}） ------")

        with requests.Session() as s:
            try:
                access_token = resolve_access_token(s, start_url, user.token, timeout=timeout)
                print("拿到 accessToken 成功")

                doing = fetch_doing_list(s, access_token, timeout=timeout)
                if not doing:
                    print("当前没有 doing 状态的题目")
                    continue

                first = doing[0] or {}
                qid = first.get("id")
                title = first.get("topic")

                submit_res = submit_answer(s, access_token, int(qid), timeout=timeout)

                tips = ((submit_res.get("result") or {}).get("tips")) if isinstance(submit_res, dict) else None
                msg = tips or submit_res.get("message") or "提交完成"
                print(f"自动答题完成：{title}，提交结果：{msg}")

            except Exception as e:
                print(f"处理用户 {user.name} 出错: {e}")
                continue


def main():
    log_line("[INFO] [night_answer_server] 自动夜答服务已启动")
    scheduler = BlockingScheduler(timezone=TZ)

    scheduler.add_job(
        task,
        trigger=IntervalTrigger(minutes=5, timezone=TZ),
        id="night_answer_interval",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    print("scheduler started:", datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"))
    now = datetime.now(TZ)
    for job in scheduler.get_jobs():
        trigger = job.trigger
        next_time = trigger.get_next_fire_time(None, now)
        print(job.id, next_time, next_time.tzinfo)
    scheduler.start()


if __name__ == "__main__":
    main()