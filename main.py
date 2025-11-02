import logging
from fm_api import FMApi
from oss_client import OSSClient
from order_handler import OrderHandler

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")

    fm = FMApi()
    oss = OSSClient(fm.session, fm.token)
    handler = OrderHandler(fm, oss)

    # 示例：
    # step 1. 获取待处理工单
    need_deal = fm.get_need_deal_list()['records']

    # step 2. 批量处理
    handler.handle_all_orders(need_deal)
