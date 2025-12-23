from datetime import datetime

# 消防通道
def order_template_XFTD(order_id, marked_image1, marked_image2):
    return {
        "orderId": order_id,
        "formData": {
            "stepResult": [
                {
                    "stepNo": "1",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image1
                },
                {
                    "stepNo": "2",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "3",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "4",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "5",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image2
                },
                {
                    "stepNo": "6",
                    "stepType": "DESCRIBE",
                    "stepResult": "无"
                }
            ]
        }
    }


# 4乱2扰
def order_template_4L2R(order_id, marked_image1, marked_image2):
    return {
        "orderId": order_id,
        "formData": {
            "stepResult": [
                {
                    "stepNo": "1",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image1
                },
                {
                    "stepNo": "2",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "3",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "4",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "5",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "6",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "7",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "8",
                    "stepType": "DESCRIBE",
                    "stepResult": "无"
                },
                {
                    "stepNo": "9",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image2
                },
                {
                    "stepNo": "10",
                    "stepType": "DESCRIBE",
                    "stepResult": "无"
                }
            ]
        }
    }


# 公共区域风险 workResult
def order_template_GGQY(order_id, marked_image1, marked_image2):
    return {
        "orderId": order_id,
        "formData": {
            "stepResult": [
                {
                    "stepNo": "1",
                    "stepType": "ONECHOOSE",
                    "stepResult": "否"
                },
                {
                    "stepNo": "1.2",
                    "stepType": "WRITE",
                    "stepResult": "无此区域"
                },
                {
                    "stepNo": "2",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "3",
                    "stepType": "ONECHOOSE",
                    "stepResult": "否"
                },
                {
                    "stepNo": "4",
                    "stepType": "ONECHOOSE",
                    "stepResult": "是"
                },
                {
                    "stepNo": "4.1",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image1
                },
                {
                    "stepNo": "5",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "6",
                    "stepType": "ONECHOOSE",
                    "stepResult": "否"
                },
                {
                    "stepNo": "7",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "8",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "9",
                    "stepType": "ONECHOOSE",
                    "stepResult": "否"
                },
                {
                    "stepNo": "9.2",
                    "stepType": "WRITE",
                    "stepResult": "无此区域"
                },
                {
                    "stepNo": "10",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "11",
                    "stepType": "ONECHOOSE",
                    "stepResult": "否"
                },
                {
                    "stepNo": "12",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image2
                },
                {
                    "stepNo": "13",
                    "stepType": "DESCRIBE",
                    "stepResult": "无"
                }
            ]
        }
    }


# 门岗BI&5S日巡检
def order_template_5S(order_id, marked_image1, marked_image2):
    return {
        "orderId": order_id,
        "formData": {
            "stepResult": [
                {
                    "stepNo": "1",
                    "stepType": "ONECHOOSE",
                    "stepResult": "是"
                },
                {
                    "stepNo": "1.1",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image1
                },
                {
                    "stepNo": "2",
                    "stepType": "ONECHOOSE",
                    "stepResult": "是"
                },
                {
                    "stepNo": "2.1",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image2
                }
            ]
        }
    }


# 外来人员清场日巡查工单
def order_template_QC(order_id, marked_image):
    return {
        "orderId": order_id,
        "formData": {
            "stepResult": [
                {
                    "stepNo": "1",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "2",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image
                },
                {
                    "stepNo": "3",
                    "stepType": "READ",
                    "stepResult": "0"
                },
                {
                    "stepNo": "4",
                    "stepType": "DESCRIBE",
                    "stepResult": "无"
                }
            ]
        }
    }


# 消防设施月巡检
def order_template_XFSS(order_id, marked_image1, marked_image2, marked_image3, marked_image4):
    return {
        "orderId": order_id,
        "formData": {
            "stepResult": [
                {
                    "stepNo": "1",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image1
                },
                {
                    "stepNo": "2",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image2
                },
                {
                    "stepNo": "3",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image3
                },
                {
                    "stepNo": "4",
                    "stepType": "DEFAULT"
                },
                {
                    "stepNo": "5",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image4
                },
                {
                    "stepNo": "6",
                    "stepType": "DESCRIBE",
                    "stepResult": "无"
                }
            ]
        }
    }


# 单元楼月巡检
def order_template_DYL(order_id, marked_image1, marked_image2, marked_image3):
    return {
        "orderId": order_id,
        "formData": {
            "stepResult": [
                {
                    "stepNo": "1",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image1
                },
                {
                    "stepNo": "2",
                    "stepType": "ONECHOOSE",
                    "stepResult": "正常"
                },
                {
                    "stepNo": "3",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "4",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "5",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "6",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "7",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "8",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "9",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "10",
                    "stepType": "ONECHOOSE",
                    "stepResult": "正常"
                },
                {
                    "stepNo": "11",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "12",
                    "stepType": "ESTIMATE",
                    "stepResult": "0"
                },
                {
                    "stepNo": "13",
                    "stepType": "ONECHOOSE",
                    "stepResult": "正常"
                },
                {
                    "stepNo": "14",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "15",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "16",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image2
                },
                {
                    "stepNo": "17",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image3
                }
            ]
        }
    }


# 天台风险月巡查 workResult
def order_template_TTFX(order_id, marked_image1, marked_image2, marked_image3):
    return {
        "orderId": order_id,
        "formData": {
            "stepResult": [
                {
                    "stepNo": "1",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "2",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "3",
                    "stepType": "ONECHOOSE",
                    "stepResult": "是"
                },
                {
                    "stepNo": "3.1",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image1
                },
                {
                    "stepNo": "4",
                    "stepType": "ESTIMATE",
                    "stepResult": "1"
                },
                {
                    "stepNo": "5",
                    "stepType": "ONECHOOSE",
                    "stepResult": "是"
                },
                {
                    "stepNo": "5.1",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image2
                },
                {
                    "stepNo": "6",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image3
                },
                {
                    "stepNo": "7",
                    "stepType": "DESCRIBE",
                    "stepResult": "无"
                }
            ],
            "beginDealTime": None
        }
    }


# 干粉灭火器巡检 workResult
def order_template_MHQ(order_id, marked_image1):
    return {
        "orderId": order_id,
        "formData": {
            "beginDealTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stepResult": [
                {
                    "stepNo": "1",
                    "stepType": "ESTIMATE",
                    "stepResult": "0",
                    "stepDesc": "<p>检查灭火器箱体、瓶体、封铅、保险销、软管、喷嘴等部件是否变形、损坏、缺失；</p>"
                },
                {
                    "stepNo": "2",
                    "stepType": "ESTIMATE",
                    "stepResult": "1",
                    "stepDesc": "<p>检查压力表指针是否处于绿色区域；</p>"
                },
                {
                    "stepNo": "3",
                    "stepType": "PHOTOGRAPH",
                    "stepResult": marked_image1,
                    "stepDesc": "<p>对压力表指针进行拍照；</p>"
                },
                {
                    "stepNo": "4",
                    "stepType": "ESTIMATE",
                    "stepResult": "1",
                    "stepDesc": "<p>对手提式灭火器，双手握住瓶体上下颠倒摇晃数次（10-15次），防止干粉凝固；</p>"
                },
                {
                    "stepNo": "5",
                    "stepType": "DESCRIBE",
                    "stepResult": "未过期",
                    "stepDesc": "<p>检查完毕填写检查卡，若灭火器已到报废条件（出厂满10年）或检验日期过期应立即报事，并组织更换或送检。</p>"
                }
            ]
        }
    }
