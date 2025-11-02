import traceback
import logging

from fm_api import FMApi
from oss_client import OSSClient
from order_handler import OrderHandler
from Notification import Notify

notify = Notify()


def auto_grab_task():
    try:
        logging.info("开始初始化 FM API...")
        fm = FMApi()
        oss = OSSClient(fm.session, fm.token)
        handler = OrderHandler(fm, oss)

        logging.info("开始获取 FM 工单列表...")
        task_data = fm.get_task_list()
        records = task_data.get("records", [])

        if not records:
            logging.info("没有可接的工单")
            return

        success, fail = 0, 0
        for task in records:
            try:
                fm.accept_task(task['id'])
                logging.info(f"【{task['title']}】接单成功")
                success += 1
            except Exception as e:
                logging.warning(f"【{task['title']}】接单失败：{repr(e)}")
                fail += 1

        msg = f"自动接单完成：成功 {success}，失败 {fail}"
        logging.info(msg)
        notify.send(msg)

    except Exception as e:
        notify.send(f"自动接单运行出错: {repr(e)}")
        print(f">>>>>>>>>>运行出错<<<<<<<<<<")
        traceback.print_exc()
        auto_grab_task()  # 保留递归重试逻辑


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
    logging.info(">>>>>>>>>>开始获取 FM 工单列表<<<<<<<<<<")
    auto_grab_task()
