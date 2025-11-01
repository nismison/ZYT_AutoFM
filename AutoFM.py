import datetime
import json
import os
import random
import uuid
import time
import hmac
import hashlib

import requests

from GenerateWaterMark import add_watermark_to_image
from Notification import Notify
from OrderTemplate import order_template_XFTD, order_template_4L2R, order_template_GGQY, order_template_5S, \
    order_template_QC, order_template_TTFX, order_template_KZF
from Utils import Utils

utils = Utils()
notify = Notify()

BASIC_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJBQ0NFU1NfVE9LRU4iLCJjbGllbnRJZCI6IjVlOTZlYWMwNjE1MWQwY2UyZGQ5NTU0ZDdlZTE2N2NlIiwic2NvcGUiOiJhbGwgci1zdGFmZiIsInRva2VuIjoiMjQwOTg0MCIsImlhdCI6MTc2MTk4MDAzMywiZXhwIjoxNzYyNTg0ODMzfQ.ZDpbDAcxVXsWm2S8MQTDpw6nO69yaTG5kfbWRLtQV8A"


class AutoZYT:
    def __init__(self):
        # 获取FM token
        self.FETCH_TOKEN_URL = "https://chuanplus-client.onewo.com/api/client/auth/index?uri=/"
        # 获取FM工单列表
        self.FM_TASK_LIST_URL = "https://chuanplus-client.onewo.com/api/client/order/task/list/1"
        # 接取FM工单
        self.FM_TASK_ACCEPT_URL = "https://chuanplus-client.onewo.com/api/client/order/task/action/accept"
        # 获取OSS认证信息
        self.OSS_POLICY = "https://chuanplus-client.onewo.com/api/client/file/sts/sts-token"
        # 待处理工单列表
        self.NEED_DEAL_ORDER_URL = "https://chuanplus-client.onewo.com/api/client/order/task/list/2"
        # 获取工单详情
        self.GET_ORDER_DETAIL_URL = "https://chuanplus-client.onewo.com/api/client/order/task/detail/"
        # 开始处理工单
        self.START_DEAL_ORDER = "https://chuanplus-client.onewo.com/api/client/order/task/action/begin_deal"
        # 提交工单
        self.SUBMIT_ORDER_URL = "https://chuanplus-client.onewo.com/api/client/order/task/action/close"

        self.oss = {
            "host": "",
            "access_key": "",
            "signature": "",
            "policy": "",
            "dir": "",
        }

        self.token = ""

        self.fm_task_list = []
        self.fm_need_deal_list = []

        self.session = requests.Session()
        self.session.timeout = 5

        self.init_fm_token()

    def init_fm_token(self):
        print(f">>>>>>>>>>开始初始化Token<<<<<<<<<<")
        # 从SharedPref中提取的token
        basic_token = os.getenv("ZYT_TOKEN")
        if basic_token is None:
            basic_token = BASIC_TOKEN

        headers1 = {
            "User-Agent": "VKStaffAssistant-Android-6.36.0-Mozilla/5.0 (Linux; Android 12; NTH-AN00 Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Mobile Safari/537.36",
        }
        response1 = self.session.get(self.FETCH_TOKEN_URL, headers=headers1, allow_redirects=False)

        headers2 = {
            "authorization": f"Bearer {basic_token}",
        }
        response2 = self.session.get(response1.headers['Location'], headers=headers2, allow_redirects=False)

        response3 = self.session.get(response2.headers['Location'], allow_redirects=False)
        self.token = response3.cookies.get('token')
        print(f">>>>>>>>>>Token 初始化完成<<<<<<<<<<")

    # 初始化 COS 仓库（STS 临时密钥）
    def get_oss_policy(self):
        print(f"初始化 COS 仓库")

        payload = {
            "directory": "h5-app",
            "businessType": "video",
            "durationSeconds": 1800
        }

        headers = {
            'Content-Type': "application/json",
            'x-tenant': '10010',
            'Cookie': f"token={self.token}; x-tenant=10010"
        }

        response = self.session.post(self.OSS_POLICY, data=json.dumps(payload), headers=headers)

        if response.status_code != 200:
            print(f"获取 COS 临时凭证失败，重试")
            return self.get_oss_policy()

        resp_json = response.json()
        if str(resp_json.get('code')) != '200':
            print(f"获取 COS 临时凭证失败，重试")
            return self.get_oss_policy()

        data = resp_json['data']
        self.oss['tmpSecretId'] = data['tmpSecretId']
        self.oss['tmpSecretKey'] = data['tmpSecretKey']
        self.oss['sessionToken'] = data['sessionToken']
        self.oss['expiredTime'] = int(data['expiredTime'])
        self.oss['bucketName'] = data['bucketName']
        self.oss['region'] = data['region']
        self.oss['uploadUrl'] = data['uploadUrl']
        self.oss['uploadPath'] = data['uploadPath']

        print(f"COS 仓库初始化完成")

    # 上传文件到腾讯云 COS
    def upload_oss(self, file_path="C:\\Users\\27846\\Desktop\\home_fill.png"):
        if not all([
            self.oss.get('tmpSecretId'),
            self.oss.get('tmpSecretKey'),
            self.oss.get('sessionToken'),
            self.oss.get('uploadUrl'),
            self.oss.get('uploadPath')
        ]):
            self.get_oss_policy()

        print(f"开始上传图片")

        # 生成上传路径
        file_uuid = str(uuid.uuid4())
        file_ext = file_path.split(".")[-1]

        today = datetime.datetime.today()
        upload_key = f"{self.oss['uploadPath']}{today.year}/{today.month:02d}/{today.day:02d}/{file_uuid}.{file_ext}"

        # === 构造签名 ===
        secret_id = self.oss['tmpSecretId']
        secret_key = self.oss['tmpSecretKey']
        session_token = self.oss['sessionToken']
        host = self.oss['uploadUrl'].replace("https://", "")
        start_time = int(time.time())
        end_time = self.oss['expiredTime']
        sign_time = f"{start_time};{end_time}"

        # 计算签名
        sign_key = hmac.new(secret_key.encode(), sign_time.encode(), hashlib.sha1).hexdigest()
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        http_string = f"put\n/{upload_key}\n\ncontent-length={file_size}&host={host}\n"
        http_string_hash = hashlib.sha1(http_string.encode()).hexdigest()
        string_to_sign = f"sha1\n{sign_time}\n{http_string_hash}\n"
        signature = hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()

        authorization = (
            f"q-sign-algorithm=sha1"
            f"&q-ak={secret_id}"
            f"&q-sign-time={sign_time}"
            f"&q-key-time={sign_time}"
            f"&q-header-list=content-length;host"
            f"&q-url-param-list="
            f"&q-signature={signature}"
        )

        headers = {
            "Authorization": authorization,
            "x-cos-security-token": session_token,
            "Host": host,
            "Content-Type": "image/png",
            "Content-Length": str(file_size)
        }

        # === 上传文件 ===
        upload_url = f"{self.oss['uploadUrl']}/{upload_key}"

        with open(file_path, "rb") as f:
            response = self.session.put(upload_url, data=f, headers=headers)

        if response.status_code in [200, 204]:
            print(f"图片上传完成: {upload_url}")
            return upload_url
        else:
            print(f"上传失败：{response.status_code} {response.text}，重试")
            return self.upload_oss()

    # 获取fm工单待接单列表
    def get_fm_task_list(self, page_number=1):
        payload = {
            "pageNumber": page_number,
            "pageSize": 200,
            "projectList": []
        }

        headers = {
            'Content-Type': "application/json",
            'x-tenant': '10010',
            'Cookie': f"token={self.token}; x-tenant=10010"
        }

        print(f"当前第 {page_number} 页")
        try:
            response = self.session.post(self.FM_TASK_LIST_URL, data=json.dumps(payload), headers=headers, timeout=2)

            if response.status_code != 200:
                print(f"获取工单列表失败: {response.status_code}，重试")
                self.get_fm_task_list(page_number)
                return

            response_json = response.json()

            if response_json['code'] != '200':
                return

            data = response_json['data']
            total_page = int(data['pages'])
            self.fm_task_list += data['records']

            if page_number < total_page:
                self.get_fm_task_list(page_number + 1)
            else:
                print(f"获取工单列表完成: 共计 {len(self.fm_task_list)} 个工单")

        except requests.exceptions.ReadTimeout:
            print(f"获取工单列表超时，重试")
            self.get_fm_task_list(page_number)

    # fm工单接单
    def grab_fm_task(self):
        success = 0
        fail = 0

        print(f">>>>>>>>>>开始接单<<<<<<<<<<")
        for fm_task in self.fm_task_list:
            # print(f">>>>>>>>>>fm_task: {json.dumps(fm_task)}<<<<<<<<<<")
            payload = {
                "orderId": fm_task['id']
            }

            headers = {
                'Content-Type': "application/json",
                'x-tenant': '10010',
                'Cookie': f"token={self.token}; x-tenant=10010"
            }

            try:
                response = self.session.post(
                    self.FM_TASK_ACCEPT_URL,
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=5
                )

                if response.status_code != 200:
                    print(f"【{fm_task['title']}】接单失败，跳过")
                    fail += 1
                    continue

                response_json = response.json()

                if response_json['code'] == "200":
                    print(f"【{fm_task['title']}】接单成功: 单号：{payload['orderId']}")
                    success += 1
                else:
                    print(f"【{fm_task['title']}】接单失败 - {response_json['msg']}: 单号：{payload['orderId']}")
                    fail += 1

            except requests.exceptions.ReadTimeout:
                print(f"【{fm_task['title']}】接单失败，跳过")
                fail += 1
                continue

        print(f">>>>>>>>>>接单完成: 成功：{success}，失败：{fail}<<<<<<<<<<")
        if fail > 0:
            print(f">>>>>>>>>>存在失败接单，重试<<<<<<<<<<")
            self.get_fm_task_list()
            self.grab_fm_task()
        else:
            print(f">>>>>>>>>>自动接单完成<<<<<<<<<<")
            notify.send(f"已自动接取 {success} 工单")

    # 获取待处理FM工单列表
    def get_need_deal_order(self, page_num=1):
        print(f">>>>>>>>>>正在获取待处理工单: 第 {page_num} 页<<<<<<<<<<")

        payload = {
            "pageNum": page_num,
            "pageSize": 200,
            "projectList": []
        }

        headers = {
            'Content-Type': "application/json",
            'x-tenant': '10010',
            'Cookie': f"token={self.token}; x-tenant=10010"
        }

        try:
            response = self.session.post(self.NEED_DEAL_ORDER_URL, data=json.dumps(payload), headers=headers, timeout=2)
            if response.status_code != 200:
                print(f"获取待处理工单失败: {response.status_code}，重试")
                self.get_need_deal_order(page_num)
                return

            response_json = response.json()

            if response_json['code'] == "200":
                self.fm_need_deal_list += response_json['data']['records']

                if page_num < int(response_json['data']['pages']):
                    self.get_need_deal_order(page_num + 1)
                else:
                    print(f"待处理工单获取完成: {len(self.fm_need_deal_list)}")
            else:
                print(f"获取待处理工单失败: {response_json['msg']}，重试")
                self.get_need_deal_order(page_num)

        except requests.exceptions.ReadTimeout:
            print(f"获取待处理工单超时，重试")
            self.get_need_deal_order(page_num)

    # 获取工单详情
    def get_order_detail(self, order_id):
        headers = {
            'Content-Type': "application/json",
            'x-tenant': '10010',
            'Cookie': f"token={self.token}; x-tenant=10010"
        }

        try:
            response = self.session.get(f'{self.GET_ORDER_DETAIL_URL}{order_id}', headers=headers, timeout=2)

            if response.status_code != 200:
                print(f"获取工单详情失败: {order_id}，重试")
                return self.get_order_detail(order_id)
            elif response.json()['code'] != "200":
                print(f"获取工单详情失败: {order_id}，重试")
                return self.get_order_detail(order_id)
            else:
                return response.json()['data']

        except requests.exceptions.ReadTimeout:
            print(f"获取工单详情超时，重试")
            return self.get_order_detail(order_id)

    # 开始处理工单
    def start_deal_order(self, order_id):
        order_detail = self.get_order_detail(order_id)
        if order_detail['statusName'] != '已接受':
            return

        payload = {
            "orderId": order_id
        }

        headers = {
            'Content-Type': "application/json",
            'x-tenant': '10010',
            'Cookie': f"token={self.token}; x-tenant=10010"
        }

        response = self.session.post(self.START_DEAL_ORDER, data=json.dumps(payload), headers=headers, timeout=2)

        if response.status_code != 200:
            print(f"开始处理工单失败: {order_id}，重试")
            self.start_deal_order(order_id)
        elif response.json()['code'] != "200":
            print(f"开始处理工单失败: {order_id}，重试")
            self.start_deal_order(order_id)
        else:
            print(f"开始处理工单成功: {order_id}")

    # 提交工单
    def submit_order(self, order_title, submit_payload):
        headers = {
            'Content-Type': "application/json",
            'x-tenant': '10010',
            'Cookie': f"token={self.token}; x-tenant=10010"
        }

        response = self.session.post(self.SUBMIT_ORDER_URL, data=json.dumps(submit_payload), headers=headers)

        if response.status_code != 200:
            print(f"提交工单失败: {response.status_code}，重试")
            self.submit_order(order_title, submit_payload)

        elif response.json()['code'] != "200":
            print(f"提交工单失败: {response.json()['msg']}，重试")
            self.submit_order(order_title, submit_payload)

        else:
            print(f"提交工单成功: {order_title}")
            notify.send(f"工单【{order_title}】已完成")

    # 批量处理工单
    def deal_order(self):
        ttfx_is_deal = False

        for order in self.fm_need_deal_list:
            # 待验收和临时工单不用管
            if order['woType'] != 'PM':
                continue

            # ====================== 消防通道门日巡查 ======================
            if order['title'] == "消防通道门日巡查":
                # 开始处理
                print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['id']}]<<<<<<<<<<")
                self.start_deal_order(order['id'])

                # 添加水印
                if datetime.datetime.today().hour < 12:
                    # 上午消防通道工单
                    hour = 10
                    random_minute_1 = random.randint(20, 25)  # 10:20 ~ 10:25
                    random_minute_2 = random.randint(25, 30)  # 10:25 ~ 10:30
                else:
                    # 下午消防通道工单
                    hour = 14
                    random_minute_1 = random.randint(40, 45)  # 14:40 ~ 14:45
                    random_minute_2 = random.randint(45, 50)  # 14:45 ~ 14:50

                add_watermark_to_image(utils.get_random_template_file("XFTD/1"), base_time=f'{hour}:{random_minute_1}')
                oss_pic_url1 = self.upload_oss("output_watermarked.jpg")

                add_watermark_to_image(utils.get_random_template_file("XFTD/2"), base_time=f'{hour}:{random_minute_2}')
                oss_pic_url2 = self.upload_oss("output_watermarked.jpg")

                payload = order_template_XFTD(order['id'], oss_pic_url1, oss_pic_url2)

                self.submit_order(order['title'], payload)

            # ====================== 四乱二扰日巡检 ======================
            elif order['title'] == "四乱二扰日巡检（白）":
                # 开始处理
                print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['id']}]<<<<<<<<<<")
                self.start_deal_order(order['id'])

                # 添加水印
                random_minute_1 = random.randint(10, 15)  # 10:10 ~ 10:15
                random_minute_2 = random.randint(15, 20)  # 10:15 ~ 10:20

                add_watermark_to_image(utils.get_random_template_file("4L2R/1"), base_time=f'10:{random_minute_1}')
                oss_pic_url1 = self.upload_oss("output_watermarked.jpg")

                add_watermark_to_image(utils.get_random_template_file("4L2R/2"), base_time=f'10:{random_minute_2}')
                oss_pic_url2 = self.upload_oss("output_watermarked.jpg")

                payload = order_template_4L2R(order['id'], oss_pic_url1, oss_pic_url2)

                self.submit_order(order['title'], payload)

            # ====================== 公共区域风险隐患排查日巡检工单 ======================
            elif order['title'] == "公共区域风险隐患排查日巡检工单":
                # 开始处理
                print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['id']}]<<<<<<<<<<")
                self.start_deal_order(order['id'])

                random_minute_1 = random.randint(30, 35)  # 10:30 ~ 10:35
                random_minute_2 = random.randint(35, 40)  # 10:35 ~ 10:40

                # 添加水印
                add_watermark_to_image(utils.get_random_template_file("GGQY/1"), base_time=f'10:{random_minute_1}')
                oss_pic_url1 = self.upload_oss("output_watermarked.jpg")

                add_watermark_to_image(utils.get_random_template_file("GGQY/2"), base_time=f'10:{random_minute_2}')
                oss_pic_url2 = self.upload_oss("output_watermarked.jpg")

                payload = order_template_GGQY(order['id'], oss_pic_url1, oss_pic_url2)

                self.submit_order(order['title'], payload)

            # ====================== 门岗BI&5S日巡检 ======================
            elif order['title'] == "门岗BI&5S日巡检":
                # 开始处理
                print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['id']}]<<<<<<<<<<")
                self.start_deal_order(order['id'])

                random_minute_1 = random.randint(40, 45)  # 10:40 ~ 10:45
                random_minute_2 = random.randint(45, 50)  # 10:45 ~ 10:50

                # 添加水印
                add_watermark_to_image(utils.get_random_template_file("5S/1"), base_time=f'10:{random_minute_1}')
                oss_pic_url1 = self.upload_oss("output_watermarked.jpg")

                add_watermark_to_image(utils.get_random_template_file("5S/2"), base_time=f'10:{random_minute_2}')
                oss_pic_url2 = self.upload_oss("output_watermarked.jpg")

                payload = order_template_5S(order['id'], oss_pic_url1, oss_pic_url2)

                self.submit_order(order['title'], payload)

            # ====================== 外来人员清场日巡查工单 ======================
            elif order['title'] == "外来人员清场日巡查工单":
                # 开始处理
                print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['id']}]<<<<<<<<<<")
                self.start_deal_order(order['id'])

                random_minute = random.randint(50, 59)  # 10:50 ~ 10:59

                # 添加水印
                add_watermark_to_image(utils.get_random_template_file("QC"), base_time=f'10:{random_minute}')
                oss_pic_url = self.upload_oss("output_watermarked.jpg")

                payload = order_template_QC(order['id'], oss_pic_url)

                self.submit_order(order['title'], payload)

            # elif order['title'] == "天台风险月巡查":
            #     if ttfx_is_deal:
            #         continue
            #
            #     ttfx_is_deal = True
            #     # 开始处理
            #     print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['id']}]<<<<<<<<<<")
            #     self.start_deal_order(order['id'])
            #
            #     # ============= 获取楼栋号 =============
            #     # matches = re.findall(r"[a-zA-Z]\d+", order['address'])
            #     # print(f">>>>>>>>>>matches[0]: {matches[0]}<<<<<<<<<<")
            #
            #     if datetime.datetime.today().hour < 12:
            #         # 上午天台风险工单
            #         ttfx_hour = 11
            #     else:
            #         # 下午天台风险工单
            #         ttfx_hour = 15
            #
            #     random_minute1 = random.randint(10, 13)  # 11:10 ~ 11:13
            #     random_minute2 = random.randint(14, 16)  # 11:14 ~ 11:16
            #     random_minute3 = random.randint(17, 19)  # 11:17 ~ 11:19
            #
            #     # 添加水印
            #     add_watermark_to_image(utils.get_random_template_file("TTFX/1"),
            #                            base_time=f'{ttfx_hour}:{random_minute1}')
            #     oss_pic_url1 = self.upload_oss("output_watermarked.jpg")
            #
            #     add_watermark_to_image(utils.get_random_template_file("TTFX/2"),
            #                            base_time=f'{ttfx_hour}:{random_minute2}')
            #     oss_pic_url2 = self.upload_oss("output_watermarked.jpg")
            #
            #     add_watermark_to_image(utils.get_random_template_file("TTFX/3"),
            #                            base_time=f'{ttfx_hour}:{random_minute3}')
            #     oss_pic_url3 = self.upload_oss("output_watermarked.jpg")
            #
            #     objCodes.insert(5, step_info[4]['children'][0]['objCode'])
            #     wrids.insert(5, step_info[4]['children'][0]['wrId'])
            #     objCodes.insert(3, step_info[2]['children'][0]['objCode'])
            #     wrids.insert(3, step_info[2]['children'][0]['wrId'])
            #
            #     submit_data['workData']['workResult'] = order_template_TTFX(objCodes, wrids, oss_pic_url1,
            #                                                                 oss_pic_url2, oss_pic_url3)
            #
            #     self.submit_order(submit_data)
            #
            # elif order['title'] == "空置房巡查月巡检":
            #     # 开始处理
            #     print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['id']}]<<<<<<<<<<")
            #     self.start_deal_order(order['id'])
            #
            #     if datetime.datetime.today().hour < 12:
            #         continue
            #
            #     random_minute2 = random.randint(30, 33)  # 15:30 ~ 15:33
            #     random_minute3 = random.randint(34, 36)  # 15:34 ~ 15:36
            #     random_minute4 = random.randint(37, 39)  # 15:37 ~ 15:39
            #
            #     # 添加水印
            #     add_watermark_to_image(utils.get_random_template_file("KZF/2"),
            #                            base_time=f'15:{random_minute2}')
            #     oss_pic_url2 = self.upload_oss("output_watermarked.jpg")
            #
            #     add_watermark_to_image(utils.get_random_template_file("KZF/3"),
            #                            base_time=f'15:{random_minute3}')
            #     oss_pic_url3 = self.upload_oss("output_watermarked.jpg")
            #
            #     add_watermark_to_image(utils.get_random_template_file("KZF/4"),
            #                            base_time=f'15:{random_minute4}')
            #     oss_pic_url4 = self.upload_oss("output_watermarked.jpg")
            #
            #     objCodes.insert(3, step_info[2]['children'][0]['objCode'])
            #     wrids.insert(3, step_info[2]['children'][0]['wrId'])
            #
            #     submit_data['workData']['workResult'] = order_template_KZF(objCodes, wrids, f"{oss_pic_url2}123",
            #                                                                oss_pic_url2, oss_pic_url3, oss_pic_url4)
            #
            #     self.submit_order(submit_data)


if __name__ == '__main__':
    auto_zyt = AutoZYT()
    # auto_zyt.get_fm_task_list()
    # auto_zyt.grab_fm_task()
    # auto_zyt.get_need_deal_order()
    # auto_zyt.deal_order()
