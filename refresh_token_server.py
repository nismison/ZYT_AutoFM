import json
import re
import time
from datetime import datetime, timezone
from typing import Optional, Tuple
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import TZ

import requests
from peewee import DoesNotExist

from db import UserInfo
from utils.logger import log_line

BAICHUAN_AUTH_URL = "https://chuanplus-client.onewo.com/api/client/auth/index?uri=/"
# 百川 / COS token 的统一刷新阈值：10 分钟
REFRESH_THRESHOLD_SECONDS = 10 * 60
COS_STS_URL = "https://chuanplus-client.onewo.com/api/client/file/sts/sts-token"


def fetch_baichuan_token(zyt_token: str) -> Optional[Tuple[str, int]]:
    """
    根据中英通（zyt_token）获取百川 token。
    逻辑沿用你原来的 3 次请求。
    """
    try:
        # step1：获取跳转链接
        r1 = requests.get(
            BAICHUAN_AUTH_URL,
            headers={"User-Agent": "VKStaffAssistant-Android"},
            allow_redirects=False,
            timeout=10,
        )
        loc1 = r1.headers.get("Location")
        if not loc1:
            print(f"[Baichuan] step1 未返回 Location，status={r1.status_code}")
            return None

        # step2：带 Bearer zyt_token 再次跳转
        r2 = requests.get(
            loc1,
            headers={"authorization": f"Bearer {zyt_token}"},
            allow_redirects=False,
            timeout=10,
        )
        loc2 = r2.headers.get("Location")
        if not loc2:
            print(f"[Baichuan] step2 未返回 Location，status={r2.status_code}")
            return None

        # step3：最终请求，从 cookie 中取 token
        r3 = requests.get(
            loc2,
            allow_redirects=False,
            timeout=10,
        )
        baichuan_token = r3.cookies.get("token")

        # 获取 token 的过期时间
        m = re.search(r'Expires=([^;]+)', r3.headers.get("Set-Cookie"))
        expires_str = m.group(1).strip()
        dt = datetime.strptime(expires_str, "%a, %d-%b-%Y %H:%M:%S GMT")
        dt = dt.replace(tzinfo=timezone.utc)
        ts = int(dt.timestamp())

        if not baichuan_token:
            print(
                f"[Baichuan] step3 未从 cookie 中获取到 token，status={r3.status_code}"
            )
            return None

        return baichuan_token, ts
    except Exception as e:
        print(f"[Baichuan] 获取百川 token 失败：{e}")
        return None


def fetch_cos_sts(baichuan_token: str) -> Optional[dict]:
    """
    根据百川 token 获取 COS 临时访问凭证（STS）。
    使用你原本 update_cos_sts 的逻辑，不再更新环境变量。
    """
    if not baichuan_token:
        print("[COS] baichuan_token 为空，无法获取 STS")
        return None

    try:
        sts_res = requests.post(
            COS_STS_URL,
            headers={
                "Content-Type": "application/json",
                "x-tenant": "10010",
                "Cookie": f"token={baichuan_token}; x-tenant=10010",
            },
            json={
                "directory": "h5-app",
                "businessType": "video",
                "durationSeconds": 1800,
            },
            timeout=10,
        )

        try:
            data = sts_res.json()
        except Exception as e:
            print(f"[COS] 解析 STS 响应 JSON 失败: {e}, text={sts_res.text[:200]}...")
            return None

        cos_sts = data.get("data")
        print(f"{'=' * 25} COS临时访问凭证 {'=' * 25}")
        print(cos_sts)
        print("=" * 60)

        if not cos_sts:
            print(f"[COS] STS 接口未返回 data 字段或为空: {data}")
            return None

        return cos_sts

    except Exception as e:
        print(f"[COS] 请求 STS 接口失败: {e}")
        return None


def get_or_refresh_baichuan_token(user: UserInfo):
    """
    根据 user.baichuan_expires 判断是否需要刷新百川 token：
    - 如果 baichuan_token 为空，或者 baichuan_expires 为空，必定刷新
    - 如果 (baichuan_expires - 当前时间戳) < 10 分钟，则刷新
    - 否则复用当前 baichuan_token，不调用远端接口

    返回: (baichuan_token, baichuan_expires)
    失败返回: (None, None)
    """
    now_ts = int(time.time())
    expires_ts = user.baichuan_expires

    need_refresh = False

    if not user.baichuan_token or not expires_ts:
        need_refresh = True
        reason = "本地无百川 token 或无过期时间，准备刷新"
    else:
        delta = expires_ts - now_ts
        if delta < REFRESH_THRESHOLD_SECONDS:
            need_refresh = True
            reason = f"百川 token 即将过期，剩余 {delta} 秒，准备刷新"
        else:
            reason = (
                f"百川 token 剩余 {delta} 秒，大于阈值 "
                f"{REFRESH_THRESHOLD_SECONDS} 秒，暂不刷新"
            )

    print(f"[Check] 用户 {user.user_number}：{reason}")

    # 不需要刷新，直接使用数据库中的 token
    if not need_refresh:
        return user.baichuan_token, user.baichuan_expires

    # 需要刷新：通过 user.token 换取新的百川 token
    if not user.token:
        print(f"[Error] 用户 {user.user_number} user.token 为空，无法刷新百川 token")
        return None, None

    res = fetch_baichuan_token(user.token)
    if not res:
        print(f"[Error] 用户 {user.user_number} 获取百川 token 失败")
        return None, None

    baichuan_token, baichuan_expires = res

    print(
        f"[OK] 百川 token 获取成功，前 16 位：{baichuan_token[:16]}...，"
        f"expires={baichuan_expires}"
    )
    return baichuan_token, baichuan_expires


def get_or_refresh_cos_token_str(user: UserInfo, baichuan_token: str):
    """
    根据 COS STS 的 expiredTime 判断是否需要刷新 COS token：
    - 如果 user.cos_token 为空，则刷新
    - 如果从 user.cos_token 的 JSON 里解析不到 expiredTime，则刷新
    - 如果 (expiredTime - 当前时间戳) < 10 分钟，则刷新
    - 否则复用当前 cos_token，不调用远端接口

    返回：cos_token_str（JSON 字符串，不做截断）
    失败返回：None
    """
    now_ts = int(time.time())
    need_refresh = False
    reason = ""

    cos_token_str = user.cos_token

    if not cos_token_str:
        need_refresh = True
        reason = "本地无 COS token，准备刷新"
    else:
        # 从已有的 JSON 中解析 expiredTime
        try:
            cos_data = json.loads(cos_token_str)
            expires_str = cos_data.get("expiredTime")
            expires_ts = int(expires_str) if expires_str else None
        except Exception as e:
            print(
                f"[Warn] 用户 {user.user_number} 解析本地 COS token 失败，将强制刷新：{e}"
            )
            need_refresh = True
            reason = "本地 COS token 无法解析，准备刷新"
            expires_ts = None

        if not need_refresh:
            if not expires_ts:
                need_refresh = True
                reason = "本地 COS token 无过期时间，准备刷新"
            else:
                delta = expires_ts - now_ts
                if delta < REFRESH_THRESHOLD_SECONDS:
                    need_refresh = True
                    reason = f"COS token 即将过期，剩余 {delta} 秒，准备刷新"
                else:
                    reason = (
                        f"COS token 剩余 {delta} 秒，大于阈值 "
                        f"{REFRESH_THRESHOLD_SECONDS} 秒，暂不刷新"
                    )

    print(f"[Check] 用户 {user.user_number}：{reason}")

    # 不需要刷新，直接复用数据库中的 JSON 串
    if not need_refresh:
        return cos_token_str

    # 需要刷新：通过百川 token 获取新的 COS STS
    cos_sts = fetch_cos_sts(baichuan_token)
    if not cos_sts:
        print(f"[Warn] 用户 {user.user_number} COS STS 获取失败")
        return None

    expired_time = cos_sts.get("expiredTime")
    print(f"[OK] COS STS 获取成功，expiredTime={expired_time}")

    cos_token_str = json.dumps(cos_sts, ensure_ascii=False)
    print(f"[OK] COS STS JSON 生成成功，长度：{len(cos_token_str)}")
    return cos_token_str


def update_all_user_tokens():
    """
    从数据库中获取所有有 token 的用户：
    - 根据 baichuan_expires 判断是否需要刷新 baichuan_token（小于 10 分钟才刷新）
    - 根据 COS STS 的 expiredTime 判断是否需要刷新 cos_token（小于 10 分钟才刷新）
    - 将 baichuan_token / baichuan_expires / cos_token 写回 user_info 表
    """
    users = UserInfo.select().where(UserInfo.token.is_null(False) and UserInfo.token_expires > int(time.time()))

    total = users.count()
    print(f"{'=' * 25} 刷新用户 Token 开始，共 {total} 条记录 {'=' * 25}")

    updated_cnt = 0
    skipped_cnt = 0
    failed_cnt = 0

    for user in users:
        zyt_token = user.token
        if not zyt_token:
            print(f"[Skip] 用户 {user.user_number}（{user.name}） token 为空，跳过")
            skipped_cnt += 1
            continue

        print(f"\n------ 处理用户 {user.user_number}（{user.name}） ------")

        # 1. 获取 / 刷新百川 token（只有快过期时才会真正刷新）
        baichuan_token, baichuan_expires = get_or_refresh_baichuan_token(user)
        if not baichuan_token:
            print(f"[Error] 用户 {user.user_number} 无可用百川 token，跳过 STS 刷新")
            failed_cnt += 1
            continue

        # 2. 获取 / 刷新 COS STS（只有快过期时才会真正刷新）
        cos_token_str = get_or_refresh_cos_token_str(user, baichuan_token)
        if not cos_token_str:
            print(
                f"[Warn] 用户 {user.user_number} COS STS 获取失败，将只更新百川 token（如有变化）"
            )

        # 3. 写回数据库
        changed = False

        # 百川 token
        if baichuan_token != user.baichuan_token:
            user.baichuan_token = baichuan_token
            changed = True

        # 百川 token 过期时间
        if baichuan_expires and baichuan_expires != user.baichuan_expires:
            user.baichuan_expires = baichuan_expires
            changed = True

        # COS token（字段长度限制仍在这里处理）
        if cos_token_str and cos_token_str != user.cos_token:
            # UserInfo.cos_token 是 CharField(max_length=2000)，注意长度
            if len(cos_token_str) > 2000:
                print(
                    f"[Warn] COS STS JSON 长度 {len(cos_token_str)} 超过 2000，将被截断存储"
                )
                cos_token_str = cos_token_str[:2000]
            user.cos_token = cos_token_str
            changed = True

        if changed:
            user.save()
            updated_cnt += 1
            print(f"[DB] 用户 {user.user_number} Token 信息已更新到数据库")
        else:
            skipped_cnt += 1
            print(f"[DB] 用户 {user.user_number} Token 与数据库一致，无需更新")

    print("\n" + "=" * 60)
    print(f"刷新完成：成功更新 {updated_cnt} 条，跳过 {skipped_cnt} 条，失败 {failed_cnt} 条")
    print("=" * 60)


def force_update_tokens_by_user_number(user_number: str) -> None:
    """
    强制刷新指定 user_number 的百川 token 和 COS STS：
    - 不考虑本地过期时间阈值，直接调接口获取最新 token
    - 成功时写回 user_info 表中的 baichuan_token / baichuan_expires / cos_token

    使用方式示例：
        force_update_tokens_by_user_number("123456")
    """
    try:
        user = UserInfo.get(UserInfo.user_number == user_number)
    except DoesNotExist:
        raise ValueError(f"未找到 user_number={user_number} 的用户记录")

    if not user.token:
        raise ValueError(f"用户 {user.user_number} 的 token 为空，无法换取百川 token")

    # 1. 强制获取最新百川 token（不走阈值判断）
    res = fetch_baichuan_token(user.token)
    if not res:
        raise Exception("百川 token 获取失败")

    baichuan_token, baichuan_expires = res

    # 2. 强制获取最新 COS STS
    cos_sts = fetch_cos_sts(baichuan_token)
    cos_token_str = None
    if cos_sts:
        cos_token_str = json.dumps(cos_sts, ensure_ascii=False)
        if len(cos_token_str) > 2000:
            cos_token_str = cos_token_str[:2000]

    # 3. 写回数据库
    changed = False

    # 百川 token
    if baichuan_token != user.baichuan_token:
        user.baichuan_token = baichuan_token
        changed = True

    # 百川 token 过期时间
    if baichuan_expires and baichuan_expires != user.baichuan_expires:
        user.baichuan_expires = baichuan_expires
        changed = True

    # COS token
    if cos_token_str and cos_token_str != user.cos_token:
        user.cos_token = cos_token_str
        changed = True

    if changed:
        user.save()


def task():
    """
    具体任务逻辑。
    """
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] run task")

    update_all_user_tokens()


def main():
    log_line("[INFO] [refresh_token_server] token刷新服务已启动")
    scheduler = BlockingScheduler(timezone=TZ)

    scheduler.add_job(
        task,
        trigger=IntervalTrigger(minutes=5, timezone=TZ),
        id="refresh_token_interval",
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
