from AutoFM import AutoZYT

auto_zyt = AutoZYT()
print(f">>>>>>>>>>正在获取FM工单列表<<<<<<<<<<")
auto_zyt.get_fm_task_list()
auto_zyt.grab_fm_task()
