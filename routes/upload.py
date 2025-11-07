import os
import random
import tempfile
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from config import WATERMARK_STORAGE_DIR
from db import UploadRecord
from utils.generate_water_mark import add_watermark_to_image
from utils.immich import upload_to_immich_file
from utils.logger import log_line
from utils.merge import merge_images_grid
from utils.storage import generate_random_suffix, get_image_url

bp = Blueprint("upload", __name__)


@bp.route("/api/check_uploaded", methods=["GET"])
def check_uploaded():
    etag = request.args.get("etag", "").strip()
    if not etag:
        return jsonify({"success": False, "error": "缺少etag"}), 400

    record = (UploadRecord
              .select()
              .where(UploadRecord.etag == etag)
              .order_by(UploadRecord.upload_time.desc())
              .first())

    if record:
        return jsonify({
            "success": True,
            "uploaded": True,
        })
    else:
        return jsonify({"success": True, "uploaded": False})


@bp.route("/upload_with_watermark", methods=["POST"])
def upload_with_watermark():
    """上传并添加水印（支持多文件，可选合并）"""
    try:
        name = request.form.get('name')
        user_number = request.form.get('user_number')
        base_date = request.form.get('base_date')
        base_time = request.form.get('base_time')
        merge = request.form.get('merge') == "true"

        files = []
        for k in request.files.keys():
            files.extend(request.files.getlist(k))
        if not files and 'file' in request.files:
            files = [request.files['file']]

        if not all([name, user_number]) or not files:
            return jsonify({"error": "缺少必要参数(name, user_number, file)"}), 400

        # 时间基线
        if base_date and base_time:
            curr = datetime.strptime(f"{base_date} {base_time}", "%Y-%m-%d %H:%M")
        else:
            curr = datetime.now()

        result_paths = []
        temps = []
        for f in files:
            fd, ori = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            f.save(ori)
            temps.append(ori)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = generate_random_suffix()
            image_id = f"{user_number}_{ts}_{suffix}"
            out_file = os.path.join(WATERMARK_STORAGE_DIR, f"{image_id}.jpg")

            # 每张 +1~2 分钟
            curr += timedelta(minutes=random.randint(1, 2))
            tstr = curr.strftime("%H:%M")

            add_watermark_to_image(
                original_image_path=ori,
                name=name,
                user_number=user_number,
                base_date=base_date or datetime.now().strftime("%Y-%m-%d"),
                base_time=tstr,
                output_path=out_file,
            )
            result_paths.append((image_id, out_file))

        # 合并
        if merge and len(result_paths) > 1:
            merged = merge_images_grid([p for _, p in result_paths])
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = generate_random_suffix()
            merged_id = f"{user_number}_{ts}_{suffix}_merged"
            merged_file = os.path.join(WATERMARK_STORAGE_DIR, f"{merged_id}.jpg")
            merged.save(merged_file, quality=90, optimize=True)
            merged.close()
            oss_urls = [get_image_url(merged_id, 'watermark')]
        else:
            oss_urls = [get_image_url(i, 'watermark') for i, _ in result_paths]

        for p in temps:
            try:
                os.remove(p)
            except Exception:
                pass

        log_line(f"生成水印图片 {len(oss_urls)} 张（merge={merge}）")
        return jsonify({"success": True, "oss_urls": oss_urls, "count": len(oss_urls)})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/upload_to_gallery", methods=["POST"])
def upload_to_gallery():
    """上传到相册目录，并上报 Immich"""
    try:
        file = request.files.get('file')
        etag = request.form.get('etag', '')
        if not all([file, etag]):
            return jsonify({"error": "缺少必要参数(file, etag)"}), 400

        # 保留扩展名
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        result = upload_to_immich_file(tmp_path)
        os.remove(tmp_path)

        # 保存简要记录
        UploadRecord.create(
            oss_url='oss_url',
            file_size=100,
            upload_time=datetime.now(),
            etag=etag,
            width=500,
            height=500,
        )

        if isinstance(result, dict) and result.get("error"):
            return jsonify({"success": False, "error": result.get("message")}), 500
        return jsonify({"success": True, "message": "文件已成功保存"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
