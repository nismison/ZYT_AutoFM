from AutoFM import AutoZYT
from Notification import Notify

notify = Notify()


def auto_submit_task():
    try:
        auto_zyt = AutoZYT()
        auto_zyt.get_need_deal_order()
        auto_zyt.deal_order()
    except Exception as e:
        notify.send(f"运行出错: {repr(e)}")
        print(f">>>>>>>>>>运行出错: {repr(e)}<<<<<<<<<<")
        auto_submit_task()


if __name__ == '__main__':
    print(f">>>>>>>>>>开始获取待处理FM工单列表<<<<<<<<<<")
    auto_submit_task()
