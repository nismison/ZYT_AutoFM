import hashlib
import os
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
    IMMICH_EXTERNAL_HOST_ROOT,
)
from db import File, UploadSession, UploadPart

bp = Blueprint("upload_chunk", __name__)


# =========================
# 本地存储工具函数（命名规则与 merge_worker.py 保持一致）
# =========================

def ensure_immich_root():
    """
    确保 IMMICH_EXTERNAL_HOST_ROOT 目录存在。
    """
    os.makedirs(IMMICH_EXTERNAL_HOST_ROOT, exist_ok=True)


def get_chunk_path(fingerprint: str, part_number: int) -> str:
    """
    分片文件路径，规则与 merge_worker.py 完全一致：

        /immich-external-library/<fingerprint>_<part_number>.part
    """
    filename = f"{fingerprint}_{part_number}.part"
    return os.path.join(IMMICH_EXTERNAL_HOST_ROOT, filename)


def get_final_filename(fingerprint: str, file_name: str) -> str:
    """
    合并后的最终文件名（不含路径），存到 File.cos_key 中。
    与 merge_worker.py 的 get_final_file_path 配合使用：

        final_path = IMMICH_EXTERNAL_HOST_ROOT / file.cos_key
    """
    safe_name = os.path.basename(file_name)
    return f"{fingerprint}_{safe_name}"


def save_chunk_file(file_storage, dst_path: str) -> int:
    """
    保存分片到本地，返回写入字节数。
    """
    ensure_immich_root()
    tmp_path = dst_path + ".tmp"
    file_storage.save(tmp_path)
    size = os.path.getsize(tmp_path)
    os.replace(tmp_path, dst_path)
    return size


def calc_md5(path: str) -> str:
    """
    计算分片文件 MD5，用于记录到 UploadPart.etag。
    """
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


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

    返回 data 结构：
    - 已完成（秒传）：
      {
        "status": "COMPLETED",
        "fingerprint": "...",
        "file_url": "...",
      }

    - 新文件：
      {
        "status": "NEW",
        "fingerprint": "...",
        "file_name": "xxx.mp4",
        "file_size": 123456,
        "chunk_size": 5242880,
        "total_chunks": 24,
        "uploaded_chunks": [],
      }

    - 断点续传 / 正在上传：
      {
        "status": "PARTIAL" | "UPLOADING",
        "fingerprint": "...",
        "file_name": "xxx.mp4",
        "file_size": 123456,
        "chunk_size": 5242880,
        "total_chunks": 24,
        "uploaded_chunks": [1, 2, ...],
      }
    """
    data = request.get_json(force=True, silent=True) or {}

    fingerprint = data.get("fingerprint")
    file_name = data.get("file_name")
    file_size = data.get("file_size")
    chunk_size = data.get("chunk_size")
    total_chunks = data.get("total_chunks")

    if not all([fingerprint, file_name, file_size, chunk_size, total_chunks]):
        return jsonify({
            "success": False,
            "error": "缺少必要参数",
            "data": {}
        }), 400

    try:
        file_size = int(file_size)
        chunk_size = int(chunk_size)
        total_chunks = int(total_chunks)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "file_size / chunk_size / total_chunks 必须是数字",
            "data": {}
        }), 400

    try:
        with db.atomic():
            # 用 fingerprint 做去重
            final_filename = get_final_filename(fingerprint, file_name)

            file, created = File.get_or_create(
                fingerprint=fingerprint,
                defaults={
                    "file_name": file_name,
                    "file_size": file_size,
                    "cos_key": final_filename,   # 最终合并后的文件名
                    "status": FILE_STATUS_INIT,
                },
            )

            # 已经合并完成的文件，直接秒传
            if file.status == FILE_STATUS_COMPLETED and file.url:
                return jsonify({
                    "success": True,
                    "error": "",
                    "data": {
                        "status": "COMPLETED",
                        "fingerprint": fingerprint,
                        "file_url": file.url,
                    }
                })

            # 找/建 UploadSession
            session, _ = UploadSession.get_or_create(
                file=file,
                defaults={
                    "upload_id": None,            # 本地实现无用，占位
                    "chunk_size": chunk_size,
                    "total_chunks": total_chunks,
                    "uploaded_chunks": 0,
                    "status": SESSION_STATUS_UPLOADING,
                },
            )

            # 如果前端配置变化，以最新请求为准
            if session.chunk_size != chunk_size or session.total_chunks != total_chunks:
                session.chunk_size = chunk_size
                session.total_chunks = total_chunks
                session.save()

            # 查询已上传分片
            uploaded_parts = (
                UploadPart
                .select(UploadPart.part_number)
                .where(
                    (UploadPart.file == file) &
                    (UploadPart.status == "DONE")
                )
                .order_by(UploadPart.part_number)
            )
            uploaded_numbers = [p.part_number for p in uploaded_parts]

            if created:
                status = "NEW"
            else:
                status = "PARTIAL" if uploaded_numbers else "UPLOADING"

            return jsonify({
                "success": True,
                "error": "",
                "data": {
                    "status": status,
                    "fingerprint": fingerprint,
                    "file_name": file.file_name,
                    "file_size": file.file_size,
                    "chunk_size": session.chunk_size,
                    "total_chunks": session.total_chunks,
                    "uploaded_chunks": uploaded_numbers,
                }
            })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"服务器异常: {e}",
            "data": {}
        }), 500


# =========================
# 2. 单个分片上传（写入本地）
# =========================

@bp.route("/api/upload/chunk/complete", methods=["POST"])
def chunk_complete():
    """
    分片上传到本地磁盘：
    Content-Type: multipart/form-data

    表单字段：
      - fingerprint: 字符串
      - part_number: 数字（从 1 开始）
      - file: 分片二进制数据

    本接口负责：
      - 把分片写入 IMMICH_EXTERNAL_HOST_ROOT
        => /immich-external-library/<fingerprint>_<part_number>.part
      - 写入/更新 UploadPart 记录（etag = 分片 MD5）
      - 更新 UploadSession.uploaded_chunks
      - 在分片数量达到 total_chunks 时，把 Session 标记为 READY_TO_COMPLETE

    返回 data 结构：
    {
      "fingerprint": "...",
      "uploaded_chunks": 10,
      "total_chunks": 24,
      "ready_to_merge": true/false
    }
    """
    fingerprint = request.form.get("fingerprint")
    part_number = request.form.get("part_number")
    file_storage = request.files.get("file")

    if not all([fingerprint, part_number, file_storage]):
        return jsonify({
            "success": False,
            "error": "缺少必要参数（fingerprint / part_number / file）",
            "data": {}
        }), 400

    try:
        part_number = int(part_number)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "part_number 必须是数字",
            "data": {}
        }), 400

    try:
        file = File.get(File.fingerprint == fingerprint)
        session = UploadSession.get(UploadSession.file == file)
    except DoesNotExist:
        return jsonify({
            "success": False,
            "error": "上传会话不存在，请先调用 /api/upload/prepare",
            "data": {}
        }), 404

    # 写入本地分片文件
    try:
        chunk_path = get_chunk_path(fingerprint, part_number)
        save_chunk_file(file_storage, chunk_path)
        etag = calc_md5(chunk_path)
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"写入分片失败: {e}",
            "data": {}
        }), 500

    try:
        with db.atomic():
            # 幂等：同一分片多次上传，保留第一条记录即可
            try:
                UploadPart.create(
                    file=file,
                    part_number=part_number,
                    etag=etag,
                    status="DONE",
                )
            except IntegrityError:
                # 已经存在记录，视为成功
                pass

            done_count = (
                UploadPart.select()
                .where(
                    (UploadPart.file == file) &
                    (UploadPart.status == "DONE")
                )
                .count()
            )

            session.uploaded_chunks = done_count
            if done_count == session.total_chunks:
                session.status = SESSION_STATUS_READY_TO_COMPLETE
            else:
                session.status = SESSION_STATUS_UPLOADING
            session.save()

        return jsonify({
            "success": True,
            "error": "",
            "data": {
                "fingerprint": fingerprint,
                "uploaded_chunks": session.uploaded_chunks,
                "total_chunks": session.total_chunks,
                "ready_to_merge": session.status == SESSION_STATUS_READY_TO_COMPLETE,
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"服务器异常: {e}",
            "data": {}
        }), 500


# =========================
# 3. 所有分片上传完成，标记为待合并
# =========================

@bp.route("/api/upload/complete", methods=["POST"])
def upload_complete():
    """
    前端告知「所有分片都传完了」：
    {
      "fingerprint": "..."
    }

    本地实现中，这个接口只负责：
      - 校验分片数量是否完整；
      - 如果完整，把 UploadSession.status 标记为 READY_TO_COMPLETE，
        供 merge_worker.py 轮询合并。

    返回 data 结构：
    - 已合并完成（worker 已处理）：
      {
        "status": "COMPLETED",
        "file_url": "...",
        "fingerprint": "..."
      }

    - 分片齐全，等待合并：
      {
        "status": "PENDING_MERGE",
        "fingerprint": "...",
        "uploaded_chunks": 24,
        "total_chunks": 24
      }

    - 分片不完整：
      {
        "uploaded_chunks": 10,
        "total_chunks": 24
      }
    """
    data = request.get_json(force=True, silent=True) or {}
    fingerprint = data.get("fingerprint")

    if not fingerprint:
        return jsonify({
            "success": False,
            "error": "缺少 fingerprint",
            "data": {}
        }), 400

    try:
        file = File.get(File.fingerprint == fingerprint)
        session = UploadSession.get(UploadSession.file == file)
    except DoesNotExist:
        return jsonify({
            "success": False,
            "error": "上传记录不存在",
            "data": {}
        }), 404

    # 如果已经是 COMPLETED，说明 worker 已经完成合并
    if file.status == FILE_STATUS_COMPLETED and file.url:
        return jsonify({
            "success": True,
            "error": "",
            "data": {
                "status": "COMPLETED",
                "file_url": file.url,
                "fingerprint": fingerprint,
            }
        })

    # 检查分片是否齐全
    parts = (
        UploadPart.select()
        .where(
            (UploadPart.file == file) &
            (UploadPart.status == "DONE")
        )
        .order_by(UploadPart.part_number)
    )
    parts_list = list(parts)

    if len(parts_list) != session.total_chunks:
        return jsonify({
            "success": False,
            "error": "分片数量不完整，无法进入合并队列",
            "data": {
                "uploaded_chunks": len(parts_list),
                "total_chunks": session.total_chunks,
            }
        }), 400

    try:
        with db.atomic():
            session.status = SESSION_STATUS_READY_TO_COMPLETE
            session.uploaded_chunks = len(parts_list)
            session.save()

            # file.status 至少标记为 UPLOADING，合并成功后由 worker 改为 COMPLETED
            if file.status == FILE_STATUS_INIT:
                file.status = FILE_STATUS_UPLOADING
                file.save()

        return jsonify({
            "success": True,
            "error": "",
            "data": {
                "status": "PENDING_MERGE",
                "fingerprint": fingerprint,
                "uploaded_chunks": session.uploaded_chunks,
                "total_chunks": session.total_chunks,
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"更新会话状态失败: {e}",
            "data": {}
        }), 500
