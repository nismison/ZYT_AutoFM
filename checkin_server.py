import json
import random
import threading
import time
from datetime import datetime

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from wxpusher import WxPusher

from utils.logger import log_line
from config import TZ


class Notify:
    def __init__(self):
        self.uids = ['UID_0UhoJ977fvwsJhzXokMmhzgIqFRZ']
        self.token = 'AT_a5ARmQl4Mi8mCjv6xImNDesNfjSla8OW'

    def _send_sync(self, text: str) -> None:
        try:
            WxPusher.send_message(text, uids=self.uids, token=self.token)
        except Exception:
            # “尝试发送”：失败无所谓，直接吞掉
            pass

    def send(self, text: str) -> None:
        # 异步发送：不阻塞主流程
        t = threading.Thread(target=self._send_sync, args=(text,), daemon=True)
        t.start()


notify = Notify()


def load_users():
    """加载用户列表（示例结构）。"""
    user_list = [
        {
            "name": "梁振卓",
            "mobile": "19127224860",
            "device_model": "24069RA21C",
            "device_uuid": "D27C69E56B989C9A",
            "banci": "day",
        },
        {
            "name": "苏美超",
            "mobile": "19911211678",
            "device_model": "ADY-AL10",
            "device_uuid": "BAB129B3C9A3E482",
            "banci": "day",
        },
        {
            "name": "杨蒋倩",
            "mobile": "19978804634",
            "device_model": "V1962A",
            "device_uuid": "146911049E59810B",
            "banci": "day",
        },
        {
            "name": "李国刚",
            "mobile": "19968076805",
            "device_model": "NTH-AN00",
            "device_uuid": "2C2AC3F23072A923",
            "banci": "night",
        },
    ]

    # 随机打乱
    random.shuffle(user_list)

    return user_list


def generate_random_coordinates():
    """
    在指定范围内生成随机坐标
    """
    lat = round(random.uniform(22.763168, 22.764769), 6)
    lon = round(random.uniform(108.430403, 108.431633), 6)

    return {
        "c": "GCJ-02",
        "la": lat,
        "lo": lon,
        "n": ""
    }


def checkin(name, mobile, device_model, device_uuid):
    url = "https://api.vankeservice.com/api/app/staffs/saveSignedCard"

    # 获取当前时间并格式化
    current_time = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    geo_data = generate_random_coordinates()

    payload = {
        "attendances": [
            {
                "altitude": 800.0,
                "area": 1,
                "bssid": "96:03:0c:22:02:ff",
                "device_info": {
                    "app_type": "lebang",
                    "app_version": "6.36.0",
                    "cid": "0",
                    "imei": "",
                    "lac": "0",
                    "model": device_model,
                    "os_type": "android",
                    "os_version": "12",
                    "serial": "unknown",
                    "uuid": device_uuid
                },
                "faceCheckResult": 0,
                "gd_latitude": geo_data['la'],
                "gd_longitude": geo_data['lo'],
                "inspectionTime": current_time,
                "isBindPhone": True,
                "isGCJ02": True,
                "isLocalCache": True,
                "latitude": geo_data['la'],
                "longitude": geo_data['lo'],
                "mobile": mobile,
                "moodAttendanceUser": True,
                "project_code": "6055006346",
                "project_name": "Q南宁中国锦园",
                "send_time": current_time,
                "source": "lebang",
                "ssid": "Belkin_ff02220c0396",
                "su_type": 0,
                "success": True,
                "takeImageType": 0,
                "time": current_time,
                "type": "-",
                "verticalAccuracy": 0.0
            }
        ]
    }

    headers = {
        'User-Agent': "VKStaffAssistant-Android-6.36.0",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/json; charset=UTF-8",
        'X-Version': "6.36.0",
        'X-Platform': "Android",
        'X-API-Version': "20250813",
        'X-ORGC': "45010228",
        'X-Channel': "vanke",
        'X-isOld': "false",
        'X-Mobile': mobile,
    }

    response = requests.post(url, data=json.dumps(payload), headers=headers)

    if response.status_code == 200:
        response_json = response.json()

        if response_json['code'] == 0:
            notify.send(f"【{name}】自动打卡成功: {current_time}")

    else:
        notify.send(f"⚠️【{name}】自动打卡失败")


def task(user: dict):
    """
    具体任务逻辑。
    """
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] run task for {user['name']} ({user['banci']})")

    checkin(user['name'], user['mobile'], user['device_model'], user['device_uuid'])


def run_for_banci(banci: str):
    time.sleep(random.randint(60, 180))
    users = load_users()
    targets = [u for u in users if u.get("banci") == banci]
    for u in targets:
        time.sleep(random.randint(30, 60))
        try:
            task(u)
        except Exception as e:
            now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] ERROR user={u.get('name')} err={e!r}")
            notify.send(f"[{now}] ERROR user={u.get('name')} err={e!r}")


def main():
    log_line("[INFO] [checkin_server] 签到服务已启动")
    scheduler = BlockingScheduler(timezone=TZ)

    # day：07:50 / 20:01
    scheduler.add_job(
        run_for_banci,
        trigger=CronTrigger(hour=7, minute=50, timezone=TZ),
        args=["day"],
        id="day_0750",
        replace_existing=True,
        coalesce=True,  # 堆积触发时合并
        misfire_grace_time=300,  # 允许错过后 5 分钟内补跑
        max_instances=1,  # 防止重入
    )
    scheduler.add_job(
        run_for_banci,
        trigger=CronTrigger(hour=20, minute=1, timezone=TZ),
        args=["day"],
        id="day_2001",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=300,
        max_instances=1,
    )

    # night：19:50 / 08:01
    scheduler.add_job(
        run_for_banci,
        trigger=CronTrigger(hour=19, minute=50, timezone=TZ),
        args=["night"],
        id="night_1950",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=300,
        max_instances=1,
    )
    scheduler.add_job(
        run_for_banci,
        trigger=CronTrigger(hour=8, minute=1, timezone=TZ),
        args=["night"],
        id="night_0801",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=300,
        max_instances=1,
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
