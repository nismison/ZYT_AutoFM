import json
import os
import re
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request

from apis.fm_api import FMApi
from config import TZ
from db import UserInfo, UserTemplatePic
from order_handler import OrderHandler, ORDER_RULES
from oss_client import OSSClient
from utils.crypter import generate_random_coordinates
from utils.custom_raise import *

from typing import Tuple, Dict, Any

bp = Blueprint("fm", __name__)


# 完成工单
@bp.route("/api/fm/complete", methods=["POST"])
def complete_fm():
    payload = request.get_json(silent=True) or {}
    keyword = (payload.get("keyword", "") or "").strip()
    order_id = (payload.get("order_id", "") or "").strip()
    user_name = (payload.get("user_name", "") or "").strip()
    user_number = (payload.get("user_number", "") or "").strip()

    if not all([user_name, user_number]):
        return jsonify({
            "success": False,
            "error": "缺少参数",
            "code": "INVALID_PARAM"
        }), 400

    if all([keyword, order_id]):
        return jsonify({
            "success": False,
            "error": "keyword和order_id不能同时使用",
            "code": "ORDER_ALREADY_PROCESSED"
        }), 400

    if not keyword and not order_id:
        return jsonify({
            "success": False,
            "error": "缺少参数",
            "code": "INVALID_PARAM"
        }), 400

    fm = FMApi()
    oss = OSSClient(fm.session, fm.token)
    handler = OrderHandler(fm, oss)
    records = fm.get_need_deal_list()

    try:
        result = None
        if keyword:
            result = handler.complete_order_by_keyword(records, keyword, user_name, user_number)
        if order_id:
            result = handler.complete_order_by_id(records, order_id, user_name, user_number)
        if result:
            return jsonify({
                "success": True,
                "error": "",
                "data": result,
            })
        else:
            return jsonify({
                "success": False,
                "error": "未找到工单",
                "code": "ORDER_NOT_FOUND"
            }), 500
    except OrderNotFoundError as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    except UserNotFoundError as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    except (RuleNotFoundError, ImageUploadError, PartialUploadError) as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@bp.route("/api/fm/users", methods=["POST"])
def users_fm():
    try:
        users = list(UserInfo.select())
        items = [
            {
                "id": u.id,
                "name": u.name,
                "userNumber": u.user_number,
                "phone": u.phone or "",
                "device_model": u.device_model or "",
                "device_id": u.device_id or "",
                "expired": not u.token_expires or not u.baichuan_token or u.token_expires < round(
                    datetime.now(TZ).timestamp()) or u.baichuan_expires < round(datetime.now(TZ).timestamp()),
            }
            for u in users
        ]

        return jsonify({
            "success": True,
            "data": {
                "items": items
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 获取待接单工单
@bp.route("/api/fm/pending_accept", methods=["POST"])
def pending_accept_fm():
    try:
        payload = request.get_json(silent=True) or {}
        user_number = payload.get("user_number", None)
        if user_number is None:
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        fm = FMApi(user_number=user_number)
        records = fm.get_task_list()
        return jsonify({
            "success": True,
            "data": {
                "items": records.get("records", [])
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 获取待处理工单
@bp.route("/api/fm/pending_process", methods=["POST"])
def pending_process_fm():
    try:
        payload = request.get_json(silent=True) or {}
        user_number = payload.get("user_number", None)
        if user_number is None:
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        fm = FMApi(user_number=user_number)
        records = fm.get_need_deal_list()
        return jsonify({
            "success": True,
            "data": {
                "items": records
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 接单
@bp.route("/api/fm/accept_task", methods=["POST"])
def accept_task_fm():
    try:
        payload = request.get_json(silent=True) or {}
        user_number = payload.get("user_number", None)
        order_id = payload.get("order_id", None)
        if not all([user_number, order_id]):
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        fm = FMApi(user_number=user_number)
        data = fm.accept_task(order_id)
        return jsonify({
            "success": True,
            "data": data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 批量接单
@bp.route("/api/fm/accept_muti_task", methods=["POST"])
def accept_muti_task_fm():
    try:
        payload = request.get_json(silent=True) or {}
        user_number = payload.get("user_number", None)
        order_ids = payload.get("order_ids", [])
        if not all([user_number, order_ids]):
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        fm = FMApi(user_number=user_number)

        for order_id in order_ids:
            fm.accept_task(order_id)

        return jsonify({
            "success": True,
            "data": {}
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 打卡记录
@bp.route("/api/fm/checkin_record", methods=["POST"])
def checkin_record_fm():
    try:
        payload = request.get_json(silent=True) or {}
        user_number = payload.get("user_number", None)
        phone = payload.get("phone", "")

        if not all([user_number, phone]):
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        fm = FMApi(user_number=user_number)

        checkin_record = fm.checkin_record(phone)

        return jsonify({
            "success": True,
            "data": checkin_record
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"未知错误: {str(e)}",
            "code": "UNKNOWN_ERROR"
        }), 500


# 打卡
@bp.route("/api/fm/checkin", methods=["POST"])
def checkin_fm():
    try:
        payload = request.get_json(silent=True) or {}
        phone = payload.get("phone", "")
        device_model = payload.get("device_model", "")
        device_uuid = payload.get("device_uuid", "")

        if not all([phone, device_model, device_uuid]):
            return jsonify({
                "success": False,
                "error": "缺少参数",
            }), 500

        # 获取当前时间并格式化
        current_time = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
        geo_data = generate_random_coordinates()

        payload = {
            "attendances": [
                {
                    "altitude": 800.0,
                    "area": 1,
                    "bssid": "96:03:0c:22:02:ff",
                    "device_info": {
                        "app_type": "lebang",
                        "app_version": "6.36.0",
                        "cid": "0",
                        "imei": "",
                        "lac": "0",
                        "model": device_model,
                        "os_type": "android",
                        "os_version": "12",
                        "serial": "unknown",
                        "uuid": device_uuid
                    },
                    "faceCheckResult": 0,
                    "gd_latitude": geo_data['la'],
                    "gd_longitude": geo_data['lo'],
                    "inspectionTime": current_time,
                    "isBindPhone": True,
                    "isGCJ02": True,
                    "isLocalCache": True,
                    "latitude": geo_data['la'],
                    "longitude": geo_data['lo'],
                    "mobile": phone,
                    "moodAttendanceUser": True,
                    "project_code": "6055006346",
                    "project_name": "Q南宁中国锦园",
                    "send_time": current_time,
                    "source": "lebang",
                    "ssid": "Belkin_ff02220c0396",
                    "su_type": 0,
                    "success": True,
                    "takeImageType": 0,
                    "time": current_time,
                    "type": "-",
                    "verticalAccuracy": 0.0
                }
            ]
        }

        headers = {
            'User-Agent': "VKStaffAssistant-Android-6.36.0",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Content-Type': "application/json; charset=UTF-8",
            'X-Version': "6.36.0",
            'X-Platform': "Android",
            'X-API-Version': "20250813",
            'X-ORGC': "45010228",
            'X-Channel': "vanke",
            'X-isOld': "false",
            'X-Mobile': phone,
        }

        response = requests.post(
            url="https://api.vankeservice.com/api/app/staffs/saveSignedCard",
            data=json.dumps(payload),
            headers=headers
        )

        if response.status_code == 200:
            response_json = response.json()

            if response_json.get('code', -1) == 0:
                return jsonify({
                    "success": True,
                    "data": None
                })
            else:
                return jsonify({
                    "success": False,
                    "error": f"{response_json.get('error', '未知错误')}",
                }), 500

        else:
            return jsonify({
                "success": False,
                "error": "未知错误",
            }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"{str(e)}",
        }), 500


def resolve_order_template_path(target_order: Dict[str, Any]) -> Tuple[str, str, int]:
    """
    根据工单信息解析出数据库对应的: (category, sub_category, image_count)
    """
    title = target_order.get("title", "")
    address = target_order.get("address", "")

    # 1. 查找工单规则
    rule = None
    for key in ORDER_RULES:
        if key in title:
            rule = ORDER_RULES[key]
            break

    if not rule:
        return "", "", 0

    # 2. 提取分类
    category = rule['template']
    image_count = rule.get('image_count', 0)

    # 3. 提取子分类 (特殊逻辑：单元楼栋月巡检)
    sub_category = ""
    if title == "单元楼栋月巡检":
        matches = re.findall(r"[a-zA-Z]\d+", address)
        if matches:
            sub_category = matches[0]

    return category, sub_category, image_count


@bp.route('/api/fm/check_order_templates', methods=['POST'])
def check_order_templates():
    data = request.json
    user_number = data.get('user_number')
    order_id = data.get('order_id')

    if not user_number or not order_id:
        return jsonify({"success": False, "error": "缺少必要参数"}), 400

    try:
        # 1. 获取工单详情 (调用你现有的获取工单列表/详情的方法)
        fm = FMApi(user_number=user_number)
        target_order = fm.get_order_detail(order_id)

        # 2. 解析工单对应的模板路径
        category, sub_category, image_count = resolve_order_template_path(target_order)

        if not category:
            return jsonify({
                "success": False,
                "error": f"工单【{target_order.get('title')}】未匹配到任何模板规则"
            }), 200

        # 3. 匹配工单规则
        title = target_order.get("title", "")
        rule = next((ORDER_RULES[key] for key in ORDER_RULES if key in title), None)

        if not rule:
            return jsonify({"success": False, "error": f"未找到工单【{title}】匹配的规则"})

        category = rule['template']
        image_count = rule['image_count']
        sub_category = ""

        # 单元楼栋月巡检特殊处理：提取楼栋号
        if title == "单元楼栋月巡检":
            matches = re.findall(r"[a-zA-Z]\d+", target_order.get("address", ""))
            if matches:
                sub_category = matches[0]

        # 4. Peewee 查询数据库
        query = UserTemplatePic.select().where(
            (UserTemplatePic.user_number == user_number) &
            (UserTemplatePic.category == category) &
            (UserTemplatePic.sub_category == sub_category)
        )

        # 将查询结果转换为列表字典
        existing_pics = [
            {"sequence": p.sequence, "url": p.cos_url}
            for p in query
        ]

        # 5. 计算状态
        found_sequences = {str(p['sequence']) for p in existing_pics}
        missing_sequences = [
            str(i + 1) for i in range(image_count)
            if str(i + 1) not in found_sequences
        ]

        return jsonify({
            "success": True,
            "data": {
                "order_title": title,
                "category": category,
                "sub_category": sub_category,
                "total_required": image_count,
                "found_count": len(existing_pics),
                "is_ready": len(missing_sequences) == 0,
                "missing_sequences": missing_sequences,
                "existing_pics": existing_pics
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/api/fm/upload_template', methods=['POST'])
def upload_template_pics():
    """
    POST 接口：上传模板图片
    参数 (form-data):
        user_number: 用户编号 (必填)
        category: 模板一级分类 (必填)
        sub_category: 模板二级分类 (可选, 默认为空)
        sequence: 序列号 (必填)
        files: 文件流 (支持多文件上传)
    """
    try:
        # 1. 获取基础参数
        user_number = request.form.get('user_number')
        category = request.form.get('category')
        sub_category = request.form.get('sub_category', "")
        sequence = request.form.get('sequence')

        # 获取上传的文件列表
        uploaded_files = request.files.getlist('files')

        # 2. 基础参数校验
        if not all([user_number, category, sequence]):
            return jsonify({
                "success": False,
                "error": "Missing required parameters: user_number, category, or sequence",
                "code": "PARAM_MISSING"
            })

        if not uploaded_files:
            return jsonify({
                "success": False,
                "error": "No files uploaded",
                "code": "NO_FILES"
            })

        # 3. 初始化上传客户端
        # 注意：在实际工程中，fm 和 oss 实例建议作为全局单例或从连接池获取
        fm = FMApi(user_number=user_number)
        oss = OSSClient(fm.session, fm.token)

        success_records = []

        # 4. 循环处理每一个文件
        for file in uploaded_files:
            if file.filename == '':
                continue

            # A. 保存临时文件以便 OSSClient 读取（如果你的 OSSClient.upload 支持流，可直接传流）
            # 这里演示先存后传，上传完即刻删除
            temp_path = os.path.join("/tmp", file.filename)
            file.save(temp_path)

            try:
                # B. 执行上传
                cos_url = oss.upload(temp_path)

                # C. 写入数据库记录
                # 因为你要求同一个路径下可以存多张，所以这里直接 create
                new_pic = UserTemplatePic.create(
                    user_number=user_number,
                    category=category,
                    sub_category=sub_category,
                    sequence=sequence,
                    cos_url=cos_url
                )

                success_records.append({
                    "id": new_pic.id,
                    "url": cos_url
                })

            finally:
                # D. 清理临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        # 5. 返回结果
        return jsonify({
            "success": True,
            "data": {"uploaded_count": len(success_records), "records": success_records},
            "code": "UPLOAD_SUCCESS"
        })

    except Exception as e:
        # 记录日志等
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "INTERNAL_SERVER_ERROR"
        })


@bp.route('/api/fm/get_template_info', methods=['POST'])
def get_template_info():
    """
    动态查询接口：根据参数深度返回 子类列表 或 文件详情列表(含id和url)
    """
    params = request.get_json() if request.is_json else request.form

    user_number = params.get('user_number')
    category = params.get('category')
    sub_category = params.get('sub_category')
    sequence = params.get('sequence')

    if not user_number:
        return jsonify({
            "success": False,
            "data": {},
            "error": "user_number is required",
            "code": "PARAM_MISSING"
        })

    try:
        template_alias = {v["template"]: k for k, v in ORDER_RULES.items()}

        query_filter = [UserTemplatePic.user_number == user_number]

        # --- 场景 1: 只传了 user_number -> 返回所有一级分类列表 ---
        if not category:
            categories = UserTemplatePic.select(UserTemplatePic.category).where(*query_filter).distinct()
            return jsonify({
                "success": True,
                "data": {
                    "categories": [{
                        "code": c.category,
                        "alias": template_alias[c.category]
                    } for c in categories]},
                "error": "", "code": "SUCCESS"
            })

        # --- 场景 2: 传了 category，但没传 sub_category ---
        query_filter.append(UserTemplatePic.category == category)
        if not sub_category:
            # 检查是否有非空的二级分类
            sub_cats = UserTemplatePic.select(UserTemplatePic.sub_category).where(
                *query_filter,
                UserTemplatePic.sub_category != ""
            ).distinct()

            sub_cat_list = [sc.sub_category for sc in sub_cats]
            if sub_cat_list:
                return jsonify({
                    "success": True,
                    "data": {"sub_categories": sub_cat_list},
                    "error": "", "code": "SUCCESS"
                })

            # 如果没有二级分类，且没传 sequence，返回序号列表
            if not sequence:
                sequences = UserTemplatePic.select(UserTemplatePic.sequence).where(*query_filter).distinct()
                return jsonify({
                    "success": True,
                    "data": {"sequences": [s.sequence for s in sequences]},
                    "error": "", "code": "SUCCESS"
                })

        # --- 场景 3: 传了 sub_category，但没传 sequence ---
        if sub_category:
            query_filter.append(UserTemplatePic.sub_category == sub_category)
            if not sequence:
                sequences = UserTemplatePic.select(UserTemplatePic.sequence).where(*query_filter).distinct()
                return jsonify({
                    "success": True,
                    "data": {"sequences": [s.sequence for s in sequences]},
                    "error": "", "code": "SUCCESS"
                })

        # --- 场景 4: 路径已锁定到 sequence -> 返回文件对象列表 (含 ID 和 URL) ---
        if sequence:
            query_filter.append(UserTemplatePic.sequence == sequence)
            # 同时查询 id 和 cos_url
            files = UserTemplatePic.select(UserTemplatePic.id, UserTemplatePic.cos_url).where(*query_filter)

            # 构造包含 ID 的对象列表
            file_list = [
                {"id": f.id, "url": f.cos_url}
                for f in files
            ]

            return jsonify({
                "success": True,
                "data": {"files": file_list},
                "error": "",
                "code": "SUCCESS"
            })

    except Exception as e:
        return jsonify({
            "success": False,
            "data": {},
            "error": str(e),
            "code": "SERVER_ERROR"
        })


@bp.route('/api/fm/delete_template_pic', methods=['POST'])
def delete_template_pic():
    """
    删除接口：根据数据库 ID 删除记录
    参数 (JSON 或 Form):
        id: 数据库记录的主键 ID (必填)
    """
    # 获取参数
    params = request.get_json() if request.is_json else request.form
    pic_id = params.get('id')

    # 1. 参数校验
    if not pic_id:
        return jsonify({
            "success": False,
            "data": {},
            "error": "Parameter 'id' is required",
            "code": "PARAM_MISSING"
        })

    try:
        # 2. 执行删除操作
        # .execute() 会返回受影响的行数
        query = UserTemplatePic.delete().where(UserTemplatePic.id == pic_id)
        rows_deleted = query.execute()

        if rows_deleted > 0:
            return jsonify({
                "success": True,
                "data": {"deleted_id": pic_id},
                "error": "",
                "code": "SUCCESS"
            })
        else:
            # 如果 ID 不存在，返回成功但提示未找到记录（或者也可以根据业务定义为失败）
            return jsonify({
                "success": False,
                "data": {},
                "error": "Record not found",
                "code": "NOT_FOUND"
            })

    except Exception as e:
        return jsonify({
            "success": False,
            "data": {},
            "error": str(e),
            "code": "SERVER_ERROR"
        })
