from math import ceil
from flask import Blueprint, jsonify, request
from db import UploadRecord

bp = Blueprint("gallery", __name__)


@bp.route("/api/favorite/<int:record_id>", methods=["POST"])
def toggle_favorite(record_id):
    try:
        rec = UploadRecord.get_by_id(record_id)
        rec.favorite = not rec.favorite
        rec.save()
        return jsonify({"success": True, "favorite": rec.favorite, "message": f"已{'收藏' if rec.favorite else '取消收藏'}"})
    except UploadRecord.DoesNotExist:
        return jsonify({"success": False, "error": "记录不存在"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/api/favorites", methods=["GET"])
def get_favorites():
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 20))
    q = UploadRecord.select().where(UploadRecord.favorite == True).order_by(UploadRecord.upload_time.desc())
    total = q.count()
    total_pages = max(ceil(total / size), 1)
    rows = q.paginate(page, size)
    devices = [d[0] for d in UploadRecord.select(UploadRecord.device_model).distinct().tuples() if d[0]]

    return jsonify({
        "success": True,
        "data": {
            "records": [{
                "id": r.id,
                "oss_url": r.oss_url,
                "filename": r.original_filename,
                "device_model": r.device_model,
                "upload_time": r.upload_time,
                "file_size": r.file_size,
                "favorite": r.favorite,
                "etag": r.etag,
                "width": r.width,
                "height": r.height,
                "thumb": r.thumb,
            } for r in rows],
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "devices": devices,
        }
    })


@bp.route("/api/gallery", methods=["GET"])
def api_gallery():
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 20))
    device = request.args.get("device", "").strip()

    q = UploadRecord.select().order_by(UploadRecord.upload_time.desc())
    if device:
        q = q.where(UploadRecord.device_model == device)

    total = q.count()
    total_pages = max(ceil(total / size), 1)
    rows = q.paginate(page, size)
    devices = [d[0] for d in UploadRecord.select(UploadRecord.device_model).distinct().tuples() if d[0]]

    return jsonify({
        "success": True,
        "data": {
            "records": [{
                "id": r.id,
                "oss_url": r.oss_url,
                "filename": r.original_filename,
                "device_model": r.device_model,
                "upload_time": r.upload_time,
                "file_size": r.file_size,
                "favorite": r.favorite,
                "etag": r.etag,
                "width": r.width,
                "height": r.height,
                "thumb": r.thumb,
            } for r in rows],
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "devices": devices,
        }
    })