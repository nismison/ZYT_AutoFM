import traceback

from flask import Blueprint, request, jsonify
from peewee import IntegrityError, DoesNotExist

from config import (
    db,
    FILE_STATUS_COMPLETED,
    FILE_STATUS_INIT,
    FILE_STATUS_UPLOADING,
    SESSION_STATUS_UPLOADING,
    SESSION_STATUS_READY_TO_COMPLETE,
    SESSION_STATUS_COMPLETED,
)
from db import File, UploadSession, UploadPart
from utils.cos_utils import get_cos_client, build_cos_key, build_file_url, get_cos_sts

# 定义蓝图
bp = Blueprint("upload_chunk", __name__)


# =========================
# 基础接口：获取 STS（前端直传用）
# =========================
@bp.route("/api/sts/token", methods=["GET"])
def get_sts_token():
    """
    返回当前有效的 COS STS 信息。
    """
    try:
        sts = get_cos_sts()
        return jsonify({"success": True, "data": sts})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"获取 STS 失败: {e}"}), 500


# =========================
# 1. 准备上传 / 断点续传检查
# =========================
@bp.route("/api/upload/prepare", methods=["POST"])
def upload_prepare():
    """
    前端传入文件指纹和基本信息：
    {
      "fingerprint": "...",
      "file_name": "xxx.mp4",
      "file_size": 123456,
      "chunk_size": 5242880,
      "total_chunks": 24
    }
    返回：
    - 已完成：{status: "COMPLETED", file_url: "..."}
    - 新文件：{status: "NEW", cos_key, upload_id, uploaded_chunks: []}
    - 断点续传：{status: "PARTIAL", cos_key, upload_id, uploaded_chunks: [1,2,...]}
    """
    data = request.get_json(force=True, silent=True) or {}

    fingerprint = data.get("fingerprint")
    file_name = data.get("file_name")
    file_size = data.get("file_size")
    chunk_size = data.get("chunk_size")
    total_chunks = data.get("total_chunks")

    if not all([fingerprint, file_name, file_size, chunk_size, total_chunks]):
        return jsonify({"success": False, "error": "缺少必要参数"}), 400

    try:
        # 每次准备上传时获取一轮最新 STS（含 bucketName / uploadPath 等）
        sts = get_cos_sts()
        bucket = sts["bucketName"]

        with db.atomic():
            file, created = File.get_or_create(
                fingerprint=fingerprint,
                defaults={
                    "file_name": file_name,
                    "file_size": int(file_size),
                    "cos_key": build_cos_key(fingerprint, file_name, sts),
                    "status": FILE_STATUS_INIT,
                },
            )

            # 已经上传完成，直接秒传返回
            if file.status == FILE_STATUS_COMPLETED and file.url:
                return jsonify(
                    {
                        "success": True,
                        "status": "COMPLETED",
                        "fingerprint": fingerprint,
                        "file_url": file.url,
                    }
                )

            # 找/建上传会话
            session, sess_created = UploadSession.get_or_create(
                file=file,
                defaults={
                    "upload_id": None,
                    "chunk_size": int(chunk_size),
                    "total_chunks": int(total_chunks),
                    "uploaded_chunks": 0,
                    "status": SESSION_STATUS_UPLOADING,
                },
            )

            # 确保已经有 upload_id（第一次会去 COS 初始化分片）
            if not session.upload_id:
                cos_client = get_cos_client(sts)
                resp = cos_client.create_multipart_upload(
                    Bucket=bucket,
                    Key=file.cos_key,
                )
                session.upload_id = resp["UploadId"]
                session.status = SESSION_STATUS_UPLOADING
                session.save()

            # 查询已上传分片
            uploaded_parts = (
                UploadPart.select(UploadPart.part_number)
                .where(
                    (UploadPart.file == file)
                    & (UploadPart.status == "DONE")
                )
                .order_by(UploadPart.part_number)
            )
            uploaded_numbers = [p.part_number for p in uploaded_parts]

            if created:
                status = "NEW"
            else:
                status = "PARTIAL" if uploaded_numbers else "UPLOADING"

            return jsonify(
                {
                    "success": True,
                    "status": status,
                    "fingerprint": fingerprint,
                    "cos_key": file.cos_key,
                    "upload_id": session.upload_id,
                    "chunk_size": session.chunk_size,
                    "total_chunks": session.total_chunks,
                    "uploaded_chunks": uploaded_numbers,
                    # 可选：顺带把 STS 也返回，前端少调一次 /sts/token
                    "sts": sts,
                }
            )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"服务器异常: {e}"}), 500


# =========================
# 2. 单个分片上传完成回调
# =========================
@bp.route("/api/upload/chunk/complete", methods=["POST"])
def chunk_complete():
    """
    前端在 COS 上 upload_part 成功后回调：
    {
      "fingerprint": "...",
      "part_number": 1,
      "etag": "xxxxx"
    }
    """
    data = request.get_json(force=True, silent=True) or {}
    fingerprint = data.get("fingerprint")
    part_number = data.get("part_number")
    etag = data.get("etag")

    if not all([fingerprint, part_number, etag]):
        return jsonify({"success": False, "error": "缺少必要参数"}), 400

    try:
        part_number = int(part_number)
    except ValueError:
        return jsonify({"success": False, "error": "part_number 必须是数字"}), 400

    try:
        file = File.get(File.fingerprint == fingerprint)
        session = UploadSession.get(UploadSession.file == file)
    except DoesNotExist:
        return jsonify({"success": False, "error": "上传会话不存在"}), 404

    try:
        with db.atomic():
            # 插入分片记录（幂等：如果已存在就忽略）
            try:
                UploadPart.create(
                    file=file,
                    part_number=part_number,
                    etag=etag,
                    status="DONE",
                )
            except IntegrityError:
                # 已存在这个分片，视为成功
                pass

            # 重新统计已完成分片数量
            done_count = (
                UploadPart.select()
                .where(
                    (UploadPart.file == file)
                    & (UploadPart.status == "DONE")
                )
                .count()
            )

            session.uploaded_chunks = done_count
            if done_count == session.total_chunks:
                session.status = SESSION_STATUS_READY_TO_COMPLETE
            session.save()

        return jsonify(
            {
                "success": True,
                "fingerprint": fingerprint,
                "uploaded_chunks": session.uploaded_chunks,
                "total_chunks": session.total_chunks,
                "ready_to_complete": session.status
                                     == SESSION_STATUS_READY_TO_COMPLETE,
            }
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"服务器异常: {e}"}), 500


# =========================
# 3. 所有分片上传完成，触发合并
# =========================
@bp.route("/api/upload/complete", methods=["POST"])
def upload_complete():
    """
    前端告知「所有分片都传完了」：
    {
      "fingerprint": "..."
    }
    后端会从 DB 读取全部 part + etag 调用 COS 合并。
    """
    data = request.get_json(force=True, silent=True) or {}
    fingerprint = data.get("fingerprint")

    if not fingerprint:
        return jsonify({"success": False, "error": "缺少 fingerprint"}), 400

    try:
        file = File.get(File.fingerprint == fingerprint)
        session = UploadSession.get(UploadSession.file == file)
    except DoesNotExist:
        return jsonify({"success": False, "error": "上传记录不存在"}), 404

    # 幂等处理：如果已经是 COMPLETED，直接返回
    if file.status == FILE_STATUS_COMPLETED and file.url:
        return jsonify(
            {
                "success": True,
                "status": "COMPLETED",
                "file_url": file.url,
            }
        )

    # 查询所有已完成分片
    parts = (
        UploadPart.select()
        .where(
            (UploadPart.file == file)
            & (UploadPart.status == "DONE")
        )
        .order_by(UploadPart.part_number)
    )
    parts_list = list(parts)

    if len(parts_list) != session.total_chunks:
        return jsonify(
            {
                "success": False,
                "error": "分片数量不完整，无法合并",
                "uploaded_chunks": len(parts_list),
                "total_chunks": session.total_chunks,
            }
        ), 400

    cos_parts = [
        {"PartNumber": p.part_number, "ETag": p.etag} for p in parts_list
    ]

    try:
        sts = get_cos_sts()
        bucket = sts["bucketName"]
        cos_client = get_cos_client(sts)

        resp = cos_client.complete_multipart_upload(
            Bucket=bucket,
            Key=file.cos_key,
            UploadId=session.upload_id,
            MultipartUpload={"Part": cos_parts},
        )
        # 这里可以按需检查 resp

        file_url = build_file_url(file.cos_key, sts)
        file.url = file_url
        file.status = FILE_STATUS_COMPLETED
        file.save()

        session.status = SESSION_STATUS_COMPLETED
        session.save()

        return jsonify(
            {
                "success": True,
                "status": "COMPLETED",
                "file_url": file_url,
                "cos_key": file.cos_key,
            }
        )
    except Exception as e:
        traceback.print_exc()
        # 理论上这里可以补偿性调用 head_object 判断是否实际已合并成功
        file.status = FILE_STATUS_UPLOADING  # 先退回中间状态
        file.save()
        return jsonify({"success": False, "error": f"COS 合并失败: {e}"}), 500
