import json

import requests

from apis.ql_api import QLApi

ql_api = QLApi(base_url="http://ql.zytsy.icu")


def update_baichuan_token(zyt_token):
    # 获取百川Token
    fetch_url = f"https://chuanplus-client.onewo.com/api/client/auth/index?uri=/"
    r1 = requests.get(fetch_url, headers={"User-Agent": "VKStaffAssistant-Android"}, allow_redirects=False)
    r2 = requests.get(r1.headers['Location'], headers={"authorization": f"Bearer {zyt_token}"},
                      allow_redirects=False)
    r3 = requests.get(r2.headers['Location'], allow_redirects=False)
    baichuan_token = r3.cookies.get('token')

    print(f"{'=' * 25} 百川 Token {'=' * 25}")
    print(baichuan_token)
    print("=" * 60)

    update_res = ql_api.update_env("BAICHUAN_TOKEN", baichuan_token)
    if update_res:
        print("✅ 百川Token -> 更新成功")
        return baichuan_token
    else:
        print("❌ 百川Token -> 更新失败")
        return None


def update_cos_sts(baichuan_token):
    # 获取COS临时访问凭证
    sts_res = requests.post('https://chuanplus-client.onewo.com/api/client/file/sts/sts-token',
                            headers={"Content-Type": "application/json", "x-tenant": "10010",
                                     "Cookie": f"token={baichuan_token}; x-tenant=10010"},
                            json={"directory": "h5-app", "businessType": "video", "durationSeconds": 1800})
    cos_sts = sts_res.json().get("data")

    print(f"{'=' * 25} COS临时访问凭证 {'=' * 25}")
    print(cos_sts)
    print("=" * 60)

    update_res = ql_api.update_env("COS_STS", json.dumps(cos_sts))
    if update_res:
        print("✅ COS临时访问凭证 -> 更新成功")
    else:
        print("❌ COS临时访问凭证 -> 更新失败")


if __name__ == '__main__':
    zyt_token = ql_api.get_env("ZYT_TOKEN")
    zyt_token = zyt_token.get("value")
    baichuan_token = update_baichuan_token(zyt_token)

    if baichuan_token:
        update_cos_sts(baichuan_token)
