import logging
import traceback
from datetime import datetime

from apis.fm_api import FMApi
from order_handler import OrderHandler
from oss_client import OSSClient
from utils.notification import Notify

notify = Notify()


def auto_submit_task():
    try:
        logging.info("初始化 FM API...")
        fm = FMApi()
        oss = OSSClient(fm.session, fm.token)
        handler = OrderHandler(fm, oss)

        logging.info("开始获取待处理工单列表...")
        deal_data = fm.get_need_deal_list()
        records = deal_data.get("records", [])

        if not records:
            logging.info("没有待处理的工单")
            return

        handler.handle_all_orders(records)

        # 处理完毕重新查看剩余工单
        today = datetime.today()
        month = str('{:0>2d}'.format(today.month))
        day = str('{:0>2d}'.format(today.day))

        deal_data = fm.get_need_deal_list()
        records = [r for r in deal_data.get("records", []) if r['woType'] == 'PM' and r['endDealTime'][:10] == f'2025-{month}-{day}']

        msg = f"自动提交工单任务完成，剩余 {len(records)} 条"
        logging.info(msg)
        notify.send(msg)

    except Exception as e:
        notify.send(f"自动提交运行出错: {repr(e)}")
        print(f">>>>>>>>>>运行出错<<<<<<<<<<")
        traceback.print_exc()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
    logging.info(">>>>>>>>>>开始获取待处理 FM 工单列表<<<<<<<<<<")
    auto_submit_task()
