# 消防通道 workResult
def order_template_XFTD(objCodes: list, wrids: list, marked_image: str):
    return [
        {
            "objCode": objCodes[0],
            "result": [marked_image],
            "step": "1",
            "type": "photograph",
            "wrid": wrids[0]
        },
        {
            "objCode": objCodes[1],
            "result": [
                "0"
            ],
            "step": "2",
            "type": "estimate",
            "wrid": wrids[1]
        },
        {
            "objCode": objCodes[2],
            "result": [
                "1"
            ],
            "step": "3",
            "type": "estimate",
            "wrid": wrids[2]
        },
        {
            "objCode": objCodes[3],
            "result": [
                "0"
            ],
            "step": "4",
            "type": "estimate",
            "wrid": wrids[3]
        },
        {
            "objCode": objCodes[4],
            "result": [
                "1"
            ],
            "step": "5",
            "type": "estimate",
            "wrid": wrids[4]
        },
        {
            "objCode": objCodes[5],
            "result": "无",
            "step": "6",
            "type": "describe",
            "wrid": wrids[5]
        }
    ]


# 4乱2扰 workResult
def order_template_4L2R(objCodes: list, wrids: list, marked_image1: str, marked_image2: str):
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
                "0"
            ],
            "step": "2",
            "type": "estimate",
            "wrid": wrids[1]
        },
        {
            "objCode": objCodes[2],
            "result": [
                "0"
            ],
            "step": "3",
            "type": "estimate",
            "wrid": wrids[2]
        },
        {
            "objCode": objCodes[3],
            "result": [
                "0"
            ],
            "step": "4",
            "type": "estimate",
            "wrid": wrids[3]
        },
        {
            "objCode": objCodes[4],
            "result": [
                "0"
            ],
            "step": "5",
            "type": "estimate",
            "wrid": wrids[4]
        },
        {
            "objCode": objCodes[5],
            "result": [
                "0"
            ],
            "step": "6",
            "type": "estimate",
            "wrid": wrids[5]
        },
        {
            "objCode": objCodes[6],
            "result": [
                "0"
            ],
            "step": "7",
            "type": "estimate",
            "wrid": wrids[6]
        },
        {
            "objCode": objCodes[7],
            "result": "无",
            "step": "8",
            "type": "describe",
            "wrid": wrids[7]
        },
        {
            "objCode": objCodes[8],
            "result": [
                marked_image2
            ],
            "step": "9",
            "type": "photograph",
            "wrid": wrids[8]
        },
        {
            "objCode": objCodes[9],
            "result": "无",
            "step": "10",
            "type": "describe",
            "wrid": wrids[9]
        }
    ]


# 公共区域风险 workResult
def order_template_GGQY(objCodes: list, wrids: list, marked_image1: str, marked_image2: str):
    return [
        {
            "objCode": objCodes[0],
            "result": "否",
            "step": "1",
            "type": "onechoose",
            "wrid": wrids[0]
        },
        {
            "objCode": objCodes[1],
            "result": "无此区域",
            "step": "1.2",
            "type": "write",
            "wrid": wrids[1]
        },
        {
            "objCode": objCodes[2],
            "result": [
                "0"
            ],
            "step": "2",
            "type": "estimate",
            "wrid": wrids[2]
        },
        {
            "objCode": objCodes[3],
            "result": "否",
            "step": "3",
            "type": "onechoose",
            "wrid": wrids[3]
        },
        {
            "objCode": objCodes[4],
            "result": "是",
            "step": "4",
            "type": "onechoose",
            "wrid": wrids[4]
        },
        {
            "objCode": objCodes[5],
            "result": [
                marked_image1
            ],
            "step": "4.1",
            "type": "photograph",
            "wrid": wrids[5]
        },
        {
            "objCode": objCodes[6],
            "result": [
                "1"
            ],
            "step": "5",
            "type": "estimate",
            "wrid": wrids[6]
        },
        {
            "objCode": objCodes[7],
            "result": "否",
            "step": "6",
            "type": "onechoose",
            "wrid": wrids[7]
        },
        {
            "objCode": objCodes[8],
            "result": [
                "1"
            ],
            "step": "7",
            "type": "estimate",
            "wrid": wrids[8]
        },
        {
            "objCode": objCodes[9],
            "result": [
                "1"
            ],
            "step": "8",
            "type": "estimate",
            "wrid": wrids[9]
        },
        {
            "objCode": objCodes[10],
            "result": "否",
            "step": "9",
            "type": "onechoose",
            "wrid": wrids[10]
        },
        {
            "objCode": objCodes[11],
            "result": "无此区域",
            "step": "9.2",
            "type": "write",
            "wrid": wrids[11]
        },
        {
            "objCode": objCodes[12],
            "result": [
                "0"
            ],
            "step": "10",
            "type": "estimate",
            "wrid": wrids[12]
        },
        {
            "objCode": objCodes[13],
            "result": "否",
            "step": "11",
            "type": "onechoose",
            "wrid": wrids[13]
        },
        {
            "objCode": objCodes[14],
            "result": [
                marked_image2
            ],
            "step": "12",
            "type": "photograph",
            "wrid": wrids[14]
        },
        {
            "objCode": objCodes[15],
            "result": "无",
            "step": "13",
            "type": "describe",
            "wrid": wrids[15]
        }
    ]


# 门岗BI&5S日巡检 workResult
def order_template_5S(objCodes: list, wrids: list, marked_image1: str, marked_image2: str):
    return [
        {
            "objCode": objCodes[0],
            "result": "是",
            "step": "1",
            "type": "onechoose",
            "wrid": wrids[0]
        },
        {
            "objCode": objCodes[1],
            "result": [
                marked_image1
            ],
            "step": "1.1",
            "type": "photograph",
            "wrid": wrids[1]
        },
        {
            "objCode": objCodes[2],
            "result": "是",
            "step": "2",
            "type": "onechoose",
            "wrid": wrids[2]
        },
        {
            "objCode": objCodes[3],
            "result": [
                marked_image2
            ],
            "step": "2.1",
            "type": "photograph",
            "wrid": wrids[3]
        }
    ]


# 外来人员清场日巡查工单 workResult
def order_template_QC(objCodes: list, wrids: list, marked_image: str):
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
                marked_image
            ],
            "step": "2",
            "type": "photograph",
            "wrid": wrids[1]
        },
        {
            "objCode": objCodes[2],
            "result": "0",
            "step": "3",
            "type": "read",
            "wrid": wrids[2]
        },
        {
            "objCode": objCodes[3],
            "result": "无",
            "step": "4",
            "type": "describe",
            "wrid": wrids[3]
        }
    ]
