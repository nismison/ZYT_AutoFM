import datetime
import random
import re
import uuid
import os

import requests
import json

from GenerateWaterMark import add_watermark_to_image
from OrderTemplate import order_template_XFTD, order_template_4L2R, order_template_GGQY, order_template_5S, \
    order_template_QC, order_template_TTFX, order_template_KZF
from Utils import Utils
from Notification import Notify

utils = Utils()
notify = Notify()

BASIC_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJBQ0NFU1NfVE9LRU4iLCJjbGllbnRJZCI6IjVlOTZlYWMwNjE1MWQwY2UyZGQ5NTU0ZDdlZTE2N2NlIiwic2NvcGUiOiJhbGwgci1zdGFmZiIsInRva2VuIjoiMjQwOTg0MCIsImlhdCI6MTc2MTQ0ODE4MywiZXhwIjoxNzYyMDUyOTgzfQ.GDsxLUzR-Sn_R2VhiFFRMDAO9cyt2OtpY_WBezuzWYA"


class AutoZYT:
    def __init__(self):
        # 获取FM token
        self.GO_FM_ORDER_URL = "https://fm-client.onewo.com/api/lebang/goFMWorkOrderPage.do"
        # 获取FM工单列表
        self.FM_TASK_LIST_URL = "https://fm-client.onewo.com/grab/v2/getGrabList.do"
        # 获取OSS认证信息
        self.OSS_POLICY = "https://fm-client.onewo.com/api/oss/getOssPolicy.do"
        # 待处理工单列表
        self.NEED_DEAL_ORDER_URL = "https://fm-client.onewo.com/needDeal/getNeedDealWorkOrder.do"
        # 开始处理工单
        self.START_DEAL_ORDER = "https://fm-client.onewo.com/eventOrder/startEventOrder.do"
        # 提交工单
        self.SUBMIT_ORDER_URL = "https://fm-client.onewo.com/complete/submitOrder.do"

        self.oss = {
            "host": "",
            "access_key": "",
            "signature": "",
            "policy": "",
            "dir": "",
        }

        # self.login()
        self.token = ""

        self.fm_task_list = []
        self.fm_need_deal_list = []

        self.init_fm_token()

    def init_fm_token(self):
        print(f">>>>>>>>>>开始初始化Token<<<<<<<<<<")
        # 从SharedPref中提取的token
        basic_token = os.getenv("ZYT_TOKEN")
        if basic_token is None:
            basic_token = BASIC_TOKEN

        params1 = {
            "wkwebview": "true",
            "queryType": "list",
            "queryValue": "45010228",
            "woType": "OD"
        }
        headers1 = {
            "User-Agent": "VKStaffAssistant-Android-6.36.0-Mozilla/5.0 (Linux; Android 12; NTH-AN00 Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Mobile Safari/537.36",
        }
        response1 = requests.get(self.GO_FM_ORDER_URL, params=params1, headers=headers1, allow_redirects=False)

        headers2 = {
            "authorization": f"Bearer {basic_token}",
        }
        response2 = requests.get(response1.headers['Location'], headers=headers2, allow_redirects=False)

        response3 = requests.get(response2.headers['Location'], allow_redirects=False)
        self.token = response3.cookies.get('TokenFM')
        print(f">>>>>>>>>>Token 初始化完成<<<<<<<<<<")

    # 初始化oss仓库
    def get_oss_policy(self):
        print(f"初始化 OSS 仓库")

        headers = {
            'Authorization': self.token,
        }

        response = requests.get(self.OSS_POLICY, headers=headers)

        if response.status_code == 200:
            response_json = response.json()
            self.oss['host'] = response_json['data']['host']
            self.oss['access_key'] = response_json['data']['accessKeyId']
            self.oss['signature'] = response_json['data']['signature']
            self.oss['policy'] = response_json['data']['policy']
            self.oss['dir'] = response_json['data']['dir']

            print(f"OSS 仓库初始化完成")

    # 上传oss
    def upload_oss(self, file_path="C:\\Users\\27846\\Desktop\\home_fill.png"):
        self.get_oss_policy()

        print(f"开始上传图片")

        # 生成一个随机的UUID
        file_uuid = (str(uuid.uuid4()))
        file_ext = file_path.split(".")[-1]

        today = datetime.datetime.today()
        now = today.time()
        month = str('{:0>2d}'.format(today.month))
        day = str('{:0>2d}'.format(today.day))
        hour = str('{:0>2d}'.format(now.hour))
        minute = str('{:0>2d}'.format(now.minute))
        second = str('{:0>2d}'.format(now.second))

        payload = {
            'OSSAccessKeyId': self.oss['access_key'],
            'signature': self.oss['signature'],
            'policy': self.oss['policy'],
            'key': f'{self.oss["dir"]}{today.year}/{month}/{day}/{hour}/{minute}/{second}/{minute}{second}/{file_uuid}.{file_ext}',
            'success_action_status': '200'
        }
        files = [
            ('file', (f'{file_uuid}.{file_ext}', open(file_path, 'rb'), 'None'))
        ]

        response = requests.post(self.oss['host'], data=payload, files=files)

        if response.status_code == 200:
            print(f"图片上传完成: https://vk-fmmob.oss-cn-shenzhen.aliyuncs.com/{payload['key']}")
            return f"https://vk-fmmob.oss-cn-shenzhen.aliyuncs.com/{payload['key']}"

    # 获取fm工单待接单列表
    def get_fm_task_list(self, page_number=1):
        payload = {
            "pageNumber": page_number,
            "pageSize": 200,
            "userOrgNodes": []
        }

        headers = {
            'Content-Type': "application/json",
            'Authorization': self.token,
        }

        print(f"当前第 {page_number} 页")
        response = requests.post(self.FM_TASK_LIST_URL, data=json.dumps(payload), headers=headers)
        response_json = response.json()

        if response_json['code'] != '200':
            return

        total_page = response_json['totalPage']
        data = response_json['data']
        self.fm_task_list += data

        if page_number < total_page:
            self.get_fm_task_list(page_number + 1)

    # fm工单接单
    def grab_fm_task(self):
        url = "https://fm-client.onewo.com/cycle/grabCycleOrder.do"

        success = 0
        fail = 0

        print(f">>>>>>>>>>开始接单<<<<<<<<<<")
        for fm_task in self.fm_task_list:
            payload = {
                "FMToken": "",
                "workOrderNo": fm_task['workOrderNo'],
                "woType": "PM",
                "projectCode": fm_task['projectCode']
            }

            headers = {
                'Authorization': self.token,
            }

            response = requests.post(url, data=json.dumps(payload), headers=headers).json()

            if response['code'] == "200":
                print(f"【{fm_task['title']}】接单成功: 单号：{payload['workOrderNo']}")
                success += 1
            else:
                print(f"【{fm_task['title']}】接单失败 - {response['msg']}: 单号：{payload['workOrderNo']}")
                fail += 1
        print(f">>>>>>>>>>接单完成: 成功：{success}，失败：{fail}<<<<<<<<<<")
        notify.send(f"已自动接取 {success} 工单，失败: {fail}")

    # 获取待处理FM工单列表
    def get_need_deal_order(self, page_num=1):
        print(f">>>>>>>>>>正在获取待处理工单: 第 {page_num} 页<<<<<<<<<<")

        payload = {
            "pageNumber": page_num,
            "projectCodes": []
        }

        headers = {
            'Content-Type': "application/json",
            'Cookie': f"TokenFM={self.token}"
        }

        response = requests.post(self.NEED_DEAL_ORDER_URL, data=json.dumps(payload), headers=headers)

        if response.status_code == 200 and response.json()['code'] == "200":
            response_json = response.json()
            self.fm_need_deal_list += response_json['data']

            if page_num < response_json['totalPage']:
                self.get_need_deal_order(page_num + 1)
            else:
                print(f"待处理工单获取完成: {len(self.fm_need_deal_list)}")
        else:
            print(f">>>>>>>>>>response.status_code: {response.status_code}<<<<<<<<<<")

    # 开始处理工单
    def start_deal_order(self, work_no, work_type, source):
        payload = {
            "wkno": work_no,
            "reqType": work_type,
            "source": source
        }
        headers = {
            'Authorization': self.token,
        }

        requests.post(self.START_DEAL_ORDER, data=json.dumps(payload), headers=headers)

    # 提交工单
    def submit_order(self, submit_payload):
        headers = {
            'Authorization': self.token,
        }

        response = requests.post(self.SUBMIT_ORDER_URL, data=json.dumps(submit_payload), headers=headers)

        if response.status_code == 200 and response.json()['code'] == '200':
            print(f">>>>>>>>>>【{submit_payload['title']}】工单提交完成<<<<<<<<<<")
            notify.send(f"工单【{submit_payload['title']}】已完成")

    # 批量处理工单
    def deal_order(self):
        ttfx_is_deal = False

        for order in self.fm_need_deal_list:
            # 待验收的临时工单不用管
            if order['status'] == '10':
                continue

            for task_info in order['taskInfoVo']:
                # 工单数据
                submit_data = {
                    "FMToken": "",
                    "projectCode": order['projectCode'],
                    "title": order['title'],
                    "workData": {
                        "FMToken": "",
                        "projectCode": order['projectCode'],
                        "title": order['title'],
                        "workOrderNo": order['workOrderNo'],
                        "workTime": order['workTime'],
                    },
                    "serviceLineCode": order['serviceLineCode'],
                    "workOrderNo": order['workOrderNo']
                }

                step_info = task_info['stepInfo']
                work_step_data = [
                    {
                        "count": len(step_info),
                        "objCode": task_info['objCode'],
                        "stepLen": len(step_info)
                    }
                ]
                submit_data['workData']['workStep'] = work_step_data

                objCodes = []
                wrids = []
                for step in step_info:
                    objCodes.append(step['objCode'])
                    wrids.append(step['wrId'])

                if order['title'] == "外围消防通道日巡查工单":
                    # 开始处理
                    print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['workOrderNo']}]<<<<<<<<<<")
                    self.start_deal_order(order['workOrderNo'], order['woType'], order['source'])

                    # 添加水印
                    if datetime.datetime.today().hour < 12:
                        # 上午消防通道工单
                        random_minute = random.randint(20, 30)  # 10:20 ~ 10:30
                        add_watermark_to_image(utils.get_random_template_file("XFTD"), base_time=f'10:{random_minute}')
                    else:
                        # 下午消防通道工单
                        random_minute = random.randint(40, 59)  # 14:40 ~ 14:59
                        add_watermark_to_image(utils.get_random_template_file("XFTD"), base_time=f'14:{random_minute}')
                    oss_pic_url = self.upload_oss("output_watermarked.jpg")

                    submit_data['workData']['workResult'] = order_template_XFTD(objCodes, wrids, oss_pic_url)

                    self.submit_order(submit_data)

                elif order['title'] == "四乱二扰日巡检（白）":
                    # 开始处理
                    print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['workOrderNo']}]<<<<<<<<<<")
                    self.start_deal_order(order['workOrderNo'], order['woType'], order['source'])

                    # 添加水印
                    random_minute_1 = random.randint(10, 15)  # 10:10 ~ 10:15
                    random_minute_2 = random.randint(15, 20)  # 10:15 ~ 10:20

                    add_watermark_to_image(utils.get_random_template_file("4L2R/1"), base_time=f'10:{random_minute_1}')
                    oss_pic_url1 = self.upload_oss("output_watermarked.jpg")

                    add_watermark_to_image(utils.get_random_template_file("4L2R/2"), base_time=f'10:{random_minute_2}')
                    oss_pic_url2 = self.upload_oss("output_watermarked.jpg")

                    submit_data['workData']['workResult'] = order_template_4L2R(objCodes, wrids, oss_pic_url1,
                                                                                oss_pic_url2)

                    self.submit_order(submit_data)

                elif order['title'] == "公共区域风险隐患排查日巡检工单":
                    # 开始处理
                    print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['workOrderNo']}]<<<<<<<<<<")
                    self.start_deal_order(order['workOrderNo'], order['woType'], order['source'])

                    random_minute_1 = random.randint(30, 35)  # 10:30 ~ 10:35
                    random_minute_2 = random.randint(35, 40)  # 10:35 ~ 10:40

                    # 添加水印
                    add_watermark_to_image(utils.get_random_template_file("GGQY/1"), base_time=f'10:{random_minute_1}')
                    oss_pic_url1 = self.upload_oss("output_watermarked.jpg")

                    add_watermark_to_image(utils.get_random_template_file("GGQY/2"), base_time=f'10:{random_minute_2}')
                    oss_pic_url2 = self.upload_oss("output_watermarked.jpg")

                    objCodes.insert(9, step_info[8]['children'][1]['objCode'])
                    wrids.insert(9, step_info[8]['children'][1]['wrId'])
                    objCodes.insert(4, step_info[3]['children'][0]['objCode'])
                    wrids.insert(4, step_info[3]['children'][0]['wrId'])
                    objCodes.insert(1, step_info[0]['children'][1]['objCode'])
                    wrids.insert(1, step_info[0]['children'][1]['wrId'])

                    submit_data['workData']['workResult'] = order_template_GGQY(objCodes, wrids, oss_pic_url1,
                                                                                oss_pic_url2)

                    self.submit_order(submit_data)

                elif order['title'] == "门岗BI&5S日巡检":
                    # 开始处理
                    print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['workOrderNo']}]<<<<<<<<<<")
                    self.start_deal_order(order['workOrderNo'], order['woType'], order['source'])

                    random_minute_1 = random.randint(40, 45)  # 10:40 ~ 10:45
                    random_minute_2 = random.randint(45, 50)  # 10:45 ~ 10:50

                    # 添加水印
                    add_watermark_to_image(utils.get_random_template_file("5S/1"), base_time=f'10:{random_minute_1}')
                    oss_pic_url1 = self.upload_oss("output_watermarked.jpg")

                    add_watermark_to_image(utils.get_random_template_file("5S/2"), base_time=f'10:{random_minute_2}')
                    oss_pic_url2 = self.upload_oss("output_watermarked.jpg")

                    objCodes.insert(2, step_info[1]['children'][0]['objCode'])
                    wrids.insert(2, step_info[1]['children'][0]['wrId'])
                    objCodes.insert(1, step_info[0]['children'][0]['objCode'])
                    wrids.insert(1, step_info[0]['children'][0]['wrId'])

                    submit_data['workData']['workResult'] = order_template_5S(objCodes, wrids, oss_pic_url1,
                                                                              oss_pic_url2)

                    self.submit_order(submit_data)

                elif order['title'] == "外来人员清场日巡查工单":
                    # 开始处理
                    print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['workOrderNo']}]<<<<<<<<<<")
                    self.start_deal_order(order['workOrderNo'], order['woType'], order['source'])

                    random_minute = random.randint(50, 59)  # 10:50 ~ 10:59

                    # 添加水印
                    add_watermark_to_image(utils.get_random_template_file("QC"), base_time=f'10:{random_minute}')
                    oss_pic_url = self.upload_oss("output_watermarked.jpg")

                    submit_data['workData']['workResult'] = order_template_QC(objCodes, wrids, oss_pic_url)

                    self.submit_order(submit_data)

                elif order['title'] == "天台风险月巡查":
                    if ttfx_is_deal:
                        continue

                    ttfx_is_deal = True
                    # 开始处理
                    print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['workOrderNo']}]<<<<<<<<<<")
                    self.start_deal_order(order['workOrderNo'], order['woType'], order['source'])

                    # ============= 获取楼栋号 =============
                    # matches = re.findall(r"[a-zA-Z]\d+", order['address'])
                    # print(f">>>>>>>>>>matches[0]: {matches[0]}<<<<<<<<<<")

                    if datetime.datetime.today().hour < 12:
                        # 上午天台风险工单
                        ttfx_hour = 11
                    else:
                        # 下午天台风险工单
                        ttfx_hour = 15

                    random_minute1 = random.randint(10, 13)  # 11:10 ~ 11:13
                    random_minute2 = random.randint(14, 16)  # 11:14 ~ 11:16
                    random_minute3 = random.randint(17, 19)  # 11:17 ~ 11:19

                    # 添加水印
                    add_watermark_to_image(utils.get_random_template_file("TTFX/1"),
                                           base_time=f'{ttfx_hour}:{random_minute1}')
                    oss_pic_url1 = self.upload_oss("output_watermarked.jpg")

                    add_watermark_to_image(utils.get_random_template_file("TTFX/2"),
                                           base_time=f'{ttfx_hour}:{random_minute2}')
                    oss_pic_url2 = self.upload_oss("output_watermarked.jpg")

                    add_watermark_to_image(utils.get_random_template_file("TTFX/3"),
                                           base_time=f'{ttfx_hour}:{random_minute3}')
                    oss_pic_url3 = self.upload_oss("output_watermarked.jpg")

                    objCodes.insert(5, step_info[4]['children'][0]['objCode'])
                    wrids.insert(5, step_info[4]['children'][0]['wrId'])
                    objCodes.insert(3, step_info[2]['children'][0]['objCode'])
                    wrids.insert(3, step_info[2]['children'][0]['wrId'])

                    submit_data['workData']['workResult'] = order_template_TTFX(objCodes, wrids, oss_pic_url1,
                                                                                oss_pic_url2, oss_pic_url3)

                    self.submit_order(submit_data)

                elif order['title'] == "空置房巡查月巡检":
                    # 开始处理
                    print(f">>>>>>>>>>开始处理工单: {order['title']}[{order['workOrderNo']}]<<<<<<<<<<")
                    self.start_deal_order(order['workOrderNo'], order['woType'], order['source'])

                    if datetime.datetime.today().hour < 12:
                        continue

                    random_minute2 = random.randint(30, 33)  # 15:30 ~ 15:33
                    random_minute3 = random.randint(34, 36)  # 15:34 ~ 15:36
                    random_minute4 = random.randint(37, 39)  # 15:37 ~ 15:39

                    # 添加水印
                    add_watermark_to_image(utils.get_random_template_file("KZF/2"),
                                           base_time=f'15:{random_minute2}')
                    oss_pic_url2 = self.upload_oss("output_watermarked.jpg")

                    add_watermark_to_image(utils.get_random_template_file("KZF/3"),
                                           base_time=f'15:{random_minute3}')
                    oss_pic_url3 = self.upload_oss("output_watermarked.jpg")

                    add_watermark_to_image(utils.get_random_template_file("KZF/4"),
                                           base_time=f'15:{random_minute4}')
                    oss_pic_url4 = self.upload_oss("output_watermarked.jpg")

                    objCodes.insert(3, step_info[2]['children'][0]['objCode'])
                    wrids.insert(3, step_info[2]['children'][0]['wrId'])

                    submit_data['workData']['workResult'] = order_template_KZF(objCodes, wrids, f"{oss_pic_url2}123",
                                                                               oss_pic_url2, oss_pic_url3, oss_pic_url4)

                    self.submit_order(submit_data)


if __name__ == '__main__':
    auto_zyt = AutoZYT()
    # auto_zyt.get_fm_task_list()
    # auto_zyt.grab_fm_task()
    auto_zyt.get_need_deal_order()
    auto_zyt.deal_order()
