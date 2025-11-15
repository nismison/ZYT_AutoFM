import os
import sys
from datetime import datetime, timedelta

from utils.notification import Notify

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from apis.immich_api import IMMICHApi

immich_api = IMMICHApi()


def get_upload_count_by_minutes(minutes):
    """
    查询过去 N 分钟内到当前时刻(UTC+8)的上传数量

    :param minutes: 要往前统计的分钟数 (int)
    :returns: 上传资源数量 (int 或 None)
    """
    now = datetime.utcnow() + timedelta(hours=8)  # 当前北京时间
    start_time = now - timedelta(minutes=minutes)

    start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    end_str = now.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    return immich_api.get_statistics(start_str, end_str)


def main():
    count = get_upload_count_by_minutes(10)
    print(f"新增资源数: {count}")
    if count is not None and count != 0:
        msg = f"新增资源数 {count}"
        Notify().send(msg)
        print("已推送通知")


if __name__ == "__main__":
    main()
