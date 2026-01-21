import json
import os
import random
import re
from datetime import datetime
from typing import Tuple, Dict, Any

import requests
from flask import Blueprint, jsonify, request

from apis.fm_api import FMApi
from config import TZ
from db import UserInfo, UserTemplatePic, CompleteTask
from order_handler import OrderHandler, ORDER_RULES
from oss_client import OSSClient
from utils.crypter import generate_random_coordinates

bp = Blueprint("fm", __name__)


# 完成工单
@bp.route("/api/fm/complete", methods=["POST"])
def complete_fm():
    payload = request.get_json(silent=True) or {}
    keyword = (payload.get("keyword", "") or "").strip()
    order_id = (payload.get("order_id", "") or "").strip()
    user_name = (payload.get("user_name", "") or "").strip()
    user_number = (payload.get("user_number", "") or "").strip()
    template_pics = (payload.get("template_pics", []) or [])

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
            result = handler.complete_order_by_keyword(records, keyword, user_name, user_number, template_pics)
        if order_id:
            result = handler.complete_order_by_id(records, order_id, user_name, user_number, template_pics)
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
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@bp.route("/api/fm/complete_task", methods=["POST"])
def create_complete_task():
    payload = request.get_json(silent=True) or {}

    keyword = (payload.get("keyword", "") or "").strip()
    order_id = (payload.get("order_id", "") or "").strip()
    user_name = (payload.get("user_name", "") or "").strip()
    user_number = (payload.get("user_number", "") or "").strip()
    template_pics = (payload.get("template_pics", []) or [])

    if not user_name or not user_number:
        return jsonify({"success": False, "error": "缺少参数", "code": "INVALID_PARAM"}), 400

    if keyword and order_id:
        return jsonify({"success": False, "error": "keyword和order_id不能同时使用", "code": "INVALID_PARAM"}), 400

    if (not keyword) and (not order_id):
        return jsonify({"success": False, "error": "缺少参数", "code": "INVALID_PARAM"}), 400

    mode = "keyword" if keyword else "id"

    task = CompleteTask.create(
        mode=mode,
        keyword=keyword or None,
        order_id=order_id or None,
        user_name=user_name,
        user_number=user_number,
        template_pics_json=json.dumps(template_pics, ensure_ascii=False),
        status="pending",
        created_at=datetime.now(TZ),
        updated_at=datetime.now(TZ),
    )

    return jsonify({
        "success": True,
        "error": "",
        "data": {"task_id": task.id, "status": task.status},
    })


@bp.route("/api/fm/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id: int):
    task = CompleteTask.get_or_none(CompleteTask.id == task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在", "code": "TASK_NOT_FOUND"}), 404

    return jsonify({
        "success": True,
        "error": "",
        "data": {
            "id": task.id,
            "status": task.status,
            "mode": task.mode,
            "keyword": task.keyword,
            "order_id": task.order_id,
            "user_name": task.user_name,
            "user_number": task.user_number,
            "template_pics_json": task.template_pics_json,
            "result_json": task.result_json,
            "error": task.error,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }
    })


@bp.route("/api/fm/tasks", methods=["GET"])
def list_tasks():
    status = (request.args.get("status") or "").strip().lower()
    user_number = (request.args.get("user_number") or "").strip()

    limit = min(int(request.args.get("limit", 20)), 100)
    offset = max(int(request.args.get("offset", 0)), 0)

    q = CompleteTask.select().order_by(CompleteTask.id.desc())
    if status:
        q = q.where(CompleteTask.status == status)
    if user_number:
        q = q.where(CompleteTask.user_number == user_number)

    total = q.count()
    items = list(q.limit(limit).offset(offset))

    return jsonify({
        "success": True,
        "error": "",
        "data": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": t.id,
                    "status": t.status,
                    "mode": t.mode,
                    "keyword": t.keyword,
                    "order_id": t.order_id,
                    "user_number": t.user_number,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                } for t in items
            ],
        }
    })


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
    try:
        params = request.json or {}
        user_number = params.get('user_number')
        order_id = params.get('order_id')

        if not user_number or not order_id:
            return jsonify({"success": False, "error": "缺少必要参数"}), 400

        # 1. 获取工单并匹配规则
        fm = FMApi(user_number=user_number)
        target_order = fm.get_order_detail(order_id)
        title = target_order.get("title", "")
        rule = next((ORDER_RULES[key] for key in ORDER_RULES if key in title), None)

        if not rule:
            return jsonify({"success": False, "error": "该工单无需模板图片"})

        category = rule['template']
        image_count = rule['image_count']
        sub_category = ""
        if title == "单元楼栋月巡检":
            matches = re.findall(r"[a-zA-Z]\d+", target_order.get("address", ""))
            if matches:
                sub_category = matches[0]

        # 2. 只查询已存在序号，用于判断是否齐全
        seq_query = UserTemplatePic.select(UserTemplatePic.sequence).where(
            (UserTemplatePic.user_number == user_number) &
            (UserTemplatePic.category == category) &
            (UserTemplatePic.sub_category == sub_category)
        )
        found_sequences = {str(p.sequence) for p in seq_query}

        missing_sequences = [
            str(i) for i in range(1, image_count + 1)
            if str(i) not in found_sequences
        ]

        is_ready = len(missing_sequences) == 0

        preview_pics = []
        if is_ready:
            # 3. 每个序号随机抽一张，带上数据库id返回给前端预览
            for seq in range(1, image_count + 1):
                candidates = list(
                    UserTemplatePic.select(
                        UserTemplatePic.id,
                        UserTemplatePic.sequence,
                        UserTemplatePic.cos_url
                    ).where(
                        (UserTemplatePic.user_number == user_number) &
                        (UserTemplatePic.category == category) &
                        (UserTemplatePic.sub_category == sub_category) &
                        (UserTemplatePic.sequence == seq)
                    )
                )

                # is_ready 为 True 时理论上不会为空，这里留一层保护
                if not candidates:
                    missing_sequences.append(str(seq))
                    is_ready = False
                    continue

                picked = random.choice(candidates)
                preview_pics.append({
                    "id": picked.id,
                    "sequence": str(picked.sequence),
                    "url": picked.cos_url,
                })

        return jsonify({
            "success": True,
            "data": {
                "category": category,
                "sub_category": sub_category,
                "is_ready": is_ready,
                "total_required": image_count,
                # 这里保持“已覆盖的序号数”，跟原先 found_sequences 语义一致
                "found_count": len(found_sequences),
                "missing_sequences": missing_sequences,
                # 齐全时给前端预览，不齐全时返回空数组
                "preview_pics": preview_pics
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
    动态查询接口：基于 ORDER_RULES 规则返回结构。
    即使数据库无记录，也保证返回完整的目录。
    """
    params = request.get_json() if request.is_json else request.form

    user_number = params.get('user_number')
    category = params.get('category')
    sub_category = params.get('sub_category')
    sequence = params.get('sequence')

    if not user_number:
        return jsonify({
            "success": False, "data": {},
            "error": "user_number is required", "code": "PARAM_MISSING"
        })

    try:
        # 1. 场景一：根目录 -> 返回所有一级分类 (基于 ORDER_RULES)
        if not category:
            # 直接从静态规则中获取所有分类
            category_list = []
            for name, rule in ORDER_RULES.items():
                category_list.append({
                    "code": rule["template"],
                    "alias": name
                })
            return jsonify({
                "success": True,
                "data": {"categories": category_list},
                "error": "", "code": "SUCCESS"
            })

        # 2. 获取当前分类对应的规则
        # 通过 template code 反查规则
        current_rule_name = next((name for name, v in ORDER_RULES.items() if v["template"] == category), None)
        if not current_rule_name:
            return jsonify({"success": False, "error": "Invalid category", "code": "INVALID_PARAM"})

        rule = ORDER_RULES[current_rule_name]
        image_count = rule["image_count"]

        # 3. 场景二：选择了 category，返回子类或序号列表
        if not sub_category:
            # 如果是 DYL (单元楼栋)，返回固定的楼栋列表
            if category == "DYL":
                return jsonify({
                    "success": True,
                    "data": {
                        "sub_categories": ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A9', 'A10', 'A11', 'A12', 'B1']},
                    "error": "", "code": "SUCCESS"
                })

            # 如果不是 DYL 且没传 sequence，说明该分类没有子类，直接返回 1 ~ image_count 序号
            if not sequence:
                return jsonify({
                    "success": True,
                    "data": {"sequences": [str(i) for i in range(1, image_count + 1)]},
                    "error": "", "code": "SUCCESS"
                })

        # 4. 场景三：传了 sub_category，返回对应的序号列表 (1 ~ image_count)
        if sub_category and not sequence:
            return jsonify({
                "success": True,
                "data": {"sequences": [str(i) for i in range(1, image_count + 1)]},
                "error": "", "code": "SUCCESS"
            })

        # 5. 场景四：路径已锁定到 sequence -> 从数据库查询真实文件列表
        if sequence:
            query_filter = [UserTemplatePic.user_number == user_number, UserTemplatePic.category == category,
                            UserTemplatePic.sequence == sequence,
                            UserTemplatePic.sub_category == (sub_category if sub_category else "")]
            # sub_category 可能为空字符串，需要匹配

            files = UserTemplatePic.select(UserTemplatePic.id, UserTemplatePic.cos_url).where(*query_filter)

            file_list = [{"id": f.id, "url": f.cos_url} for f in files]

            return jsonify({
                "success": True,
                "data": {"files": file_list},
                "error": "", "code": "SUCCESS"
            })

    except Exception as e:
        return jsonify({
            "success": False, "data": {},
            "error": str(e), "code": "SERVER_ERROR"
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
