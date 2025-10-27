import traceback

from AutoFM import AutoZYT
from Notification import Notify

notify = Notify()


def auto_grab_task():
    try:
        auto_zyt = AutoZYT()
        auto_zyt.get_fm_task_list()
        auto_zyt.grab_fm_task()
    except Exception as e:
        notify.send(f"运行出错: {repr(e)}")
        print(f">>>>>>>>>>运行出错: {traceback.print_exc()}<<<<<<<<<<")
        auto_grab_task()


if __name__ == '__main__':
    print(f">>>>>>>>>>开始获取FM工单列表<<<<<<<<<<")
    auto_grab_task()
