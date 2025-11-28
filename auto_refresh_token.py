import json
from typing import Optional

import requests

from db import UserInfo

BAICHUAN_AUTH_URL = "https://chuanplus-client.onewo.com/api/client/auth/index?uri=/"


def fetch_baichuan_token(zyt_token: str) -> Optional[str]:
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
        if not baichuan_token:
            print(
                f"[Baichuan] step3 未从 cookie 中获取到 token，status={r3.status_code}"
            )
            return None

        return baichuan_token
    except Exception as e:
        print(f"[Baichuan] 获取百川 token 失败：{e}")
        return None


COS_STS_URL = "https://chuanplus-client.onewo.com/api/client/file/sts/sts-token"


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


def update_all_user_tokens():
    """
    从数据库中获取所有有 token 的用户：
    - 使用 user.token 刷新 baichuan_token
    - 再根据 baichuan_token 获取 COS STS
    - 将 baichuan_token / cos_token 写回 user_info 表
    """
    users = UserInfo.select().where(UserInfo.token.is_null(False))

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

        # 1. 获取百川 token
        baichuan_token = fetch_baichuan_token(zyt_token)
        if not baichuan_token:
            print(f"[Error] 用户 {user.user_number} 获取百川 token 失败，跳过 STS 刷新")
            failed_cnt += 1
            continue

        print(f"[OK] 百川 token 获取成功，前 16 位：{baichuan_token[:16]}...")

        # 2. 获取 COS STS
        cos_sts = fetch_cos_sts(baichuan_token)
        if cos_sts:
            cos_token_str = json.dumps(cos_sts, ensure_ascii=False)
            print(f"[OK] COS STS 获取成功，JSON 长度：{len(cos_token_str)}")
        else:
            cos_token_str = None
            print(f"[Warn] 用户 {user.user_number} COS STS 获取失败，将只更新百川 token")

        # 3. 写回数据库
        changed = False

        if baichuan_token and baichuan_token != user.baichuan_token:
            user.baichuan_token = baichuan_token
            changed = True

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


if __name__ == '__main__':
    update_all_user_tokens()
