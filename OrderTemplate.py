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


# 天台风险月巡查 workResult
def order_template_TTFX(objCodes: list, wrids: list, marked_image1: str, marked_image2: str, marked_image3: str):
    return [
        {
            "objCode": objCodes[0],
            "result": [
                "1"
            ],
            "step": "1",
            "type": "estimate",
            "wrid": wrids[0]
        },
        {
            "objCode": objCodes[1],
            "result": [
                "1"
            ],
            "step": "2",
            "type": "estimate",
            "wrid": wrids[1]
        },
        {
            "objCode": objCodes[2],
            "result": "是",
            "step": "3",
            "type": "onechoose",
            "wrid": wrids[2]
        },
        {
            "objCode": objCodes[3],
            "result": [
                marked_image1
            ],
            "step": "3.1",
            "type": "photograph",
            "wrid": wrids[3]
        },
        {
            "objCode": objCodes[4],
            "result": [
                "1"
            ],
            "step": "4",
            "type": "estimate",
            "wrid": wrids[4]
        },
        {
            "objCode": objCodes[5],
            "result": "是",
            "step": "5",
            "type": "onechoose",
            "wrid": wrids[5]
        },
        {
            "objCode": objCodes[6],
            "result": [
                marked_image2
            ],
            "step": "5.1",
            "type": "photograph",
            "wrid": wrids[6]
        },
        {
            "objCode": objCodes[7],
            "result": [
                marked_image3
            ],
            "step": "6",
            "type": "photograph",
            "wrid": wrids[7]
        },
        {
            "objCode": objCodes[8],
            "result": "无",
            "step": "7",
            "type": "describe",
            "wrid": wrids[8]
        }
    ]


# 空置房巡查月巡检 workResult
def order_template_KZF(objCodes: list, wrids: list, marked_image1: str, marked_image2: str, marked_image3: str,
                       marked_image4: str):
    return [
        {
            "objCode": objCodes[0],
            "result": [
                marked_image1
            ],
            "step": "1",
            "type": "photograph",
            "wrid": wrids[0]
        },
        {
            "objCode": objCodes[1],
            "result": [
                marked_image2
            ],
            "step": "2",
            "type": "photograph",
            "wrid": wrids[1]
        },
        {
            "objCode": objCodes[2],
            "result": "正常",
            "step": "3",
            "type": "onechoose",
            "wrid": wrids[2]
        },
        {
            "objCode": objCodes[3],
            "result": [
                marked_image3
            ],
            "step": "3.1",
            "type": "photograph",
            "wrid": wrids[3]
        },
        {
            "objCode": objCodes[4],
            "result": [
                "0"
            ],
            "step": "4",
            "type": "estimate",
            "wrid": wrids[4]
        },
        {
            "objCode": objCodes[5],
            "result": [
                "0"
            ],
            "step": "5",
            "type": "estimate",
            "wrid": wrids[5]
        },
        {
            "objCode": objCodes[6],
            "result": [
                marked_image4
            ],
            "step": "6",
            "type": "photograph",
            "wrid": wrids[6]
        },
        {
            "objCode": objCodes[7],
            "result": "无",
            "step": "7",
            "type": "describe",
            "wrid": wrids[7]
        }
    ]
