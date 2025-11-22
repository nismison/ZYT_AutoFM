import requests

from config import QL_BASE_URL, QL_CLIENT_ID, QL_CLIENT_SECRET


class QLApi:
    def __init__(self, base_url=None):
        """
        初始化时获取 QL token
        """
        self.base_url = base_url or QL_BASE_URL.rstrip('/')
        self.client_id = QL_CLIENT_ID
        self.client_secret = QL_CLIENT_SECRET
        self.token = None
        self.token_type = None
        self.get_ql_token()

    def get_ql_token(self):
        """获取 QL token"""
        url = f"{self.base_url}/open/auth/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 200 and "data" in data:
            self.token = data["data"]["token"]
            self.token_type = data["data"]["token_type"]
        else:
            raise Exception(f"获取QL token失败: {data}")

    def _headers(self):
        """内部方法，返回带 Authorization 的请求头"""
        if not self.token or not self.token_type:
            raise Exception("QL token 未初始化")
        return {
            "Authorization": f"{self.token_type} {self.token}",
            "Content-Type": "application/json"
        }

    def get_env(self, search_value: str):
        """查询环境变量"""
        url = f"{self.base_url}/open/envs"
        params = {"searchValue": search_value}
        resp = requests.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()

        env_data = resp.json()

        if not env_data.get("data") or len(env_data["data"]) == 0:
            return None

        return env_data["data"][0]

    def update_env(self, name: str, value: str, remarks: str = "") -> bool:
        """
        更新环境变量
        自动查询第一个匹配的环境变量进行更新
        返回 True 表示更新成功
        """
        env_data = self.get_env(name)
        if not env_data:
            raise Exception(f"未找到环境变量: {name}")

        env_id = env_data["id"]
        url = f"{self.base_url}/open/envs"
        payload = {
            "id": env_id,
            "name": name,
            "value": value,
            "remarks": remarks
        }
        resp = requests.put(url, headers=self._headers(), json=payload)
        resp.raise_for_status()
        return resp.json().get("code") == 200


# 使用示例
if __name__ == "__main__":
    ql = QLApi()

    # 更新环境变量
    success = ql.update_env("ZYT_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJBQ0NFU1NfVE9LRU4iLCJjbGllbnRJZCI6IjVlOTZlYWMwNjE1MWQwY2UyZGQ5NTU0ZDdlZTE2N2NlIiwic2NvcGUiOiJhbGwgci1zdGFmZiIsInRva2VuIjoiMjQwOTg0MCIsImlhdCI6MTc2MjMxMDIwNCwiZXhwIjoxNzYyOTE1MDA0fQ.GjnFBQsGdxg8Haa2oCRVrRsIvtufsLSe1xiu6tLzzSU")
    # success = ql.update_env("ZYT_TOKEN", "new_token_value")
    print("更新成功" if success else "更新失败")
