import logging

import requests

from apis.ql_api import QLApi
from config import BASIC_TOKEN, FM_BASE_URL, HEADERS_BASE

logger = logging.getLogger(__name__)


class FMApi:
    def __init__(self):
        self.session = requests.Session()
        self.token = ""
        self.base = FM_BASE_URL
        self.init_token()

    def request(self, method, endpoint, retries=3, **kwargs):
        for i in range(retries):
            try:
                resp = self.session.request(method, endpoint, timeout=5, **kwargs)
                if resp.status_code == 200:
                    data = resp.json()
                    if str(data.get('code')) == '200':
                        return data
                logger.warning(f"请求失败({i + 1}/{retries})：{resp.text[:100]}")
            except requests.exceptions.RequestException as e:
                logger.error(f"请求异常({i + 1}/{retries})：{e}")
        raise RuntimeError(f"多次重试失败: {endpoint}")

    def init_token(self):
        logger.info("初始化Token中...")
        ql_api = QLApi()
        self.token = ql_api.get_env("BAICHUAN_TOKEN").get("value", None)
        logger.info(f"Token 初始化完成 {self.token}")

    def get_headers(self):
        headers = HEADERS_BASE.copy()
        headers["Cookie"] = f"token={self.token}; x-tenant=10010"
        return headers

    def get_task_list(self, page_number=1):
        url = f"{self.base}/order/task/list/1"
        payload = {"pageNumber": page_number, "pageSize": 200, "projectList": []}
        data = self.request("POST", url, json=payload, headers=self.get_headers())
        return data['data']

    def accept_task(self, order_id):
        url = f"{self.base}/order/task/action/accept"
        payload = {"orderId": order_id}
        return self.request("POST", url, json=payload, headers=self.get_headers())

    def get_need_deal_list(self, page_number=1):
        url = f"{self.base}/order/task/list/2"
        payload = {"pageNum": page_number, "pageSize": 200, "projectList": []}
        data = self.request("POST", url, json=payload, headers=self.get_headers())
        return data['data']

    def get_order_detail(self, order_id):
        url = f"{self.base}/order/task/detail/{order_id}"
        data = self.request("GET", url, headers=self.get_headers())
        return data['data']

    def start_order(self, order_id):
        url = f"{self.base}/order/task/action/begin_deal"
        payload = {"orderId": order_id}
        return self.request("POST", url, json=payload, headers=self.get_headers())

    def submit_order(self, payload):
        url = f"{self.base}/order/task/action/close"
        return self.request("POST", url, json=payload, headers=self.get_headers())
