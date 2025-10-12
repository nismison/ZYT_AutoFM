from AutoFM import AutoZYT

auto_zyt = AutoZYT()
print(f">>>>>>>>>>正在获取待处理FM工单列表<<<<<<<<<<")
auto_zyt.get_need_deal_order()
auto_zyt.deal_order()
