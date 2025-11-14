import os
import random
import shutil
import tempfile
from datetime import datetime, timedelta
from uuid import uuid4

import PIL.Image
from flask import Blueprint, jsonify, request, render_template
from werkzeug.utils import secure_filename

from apis.immich_api import IMMICHApi
from config import WATERMARK_STORAGE_DIR
from db import UploadRecord
from utils.generate_water_mark import add_watermark_to_image
from utils.logger import log_line
from utils.merge import merge_images_grid, resize_image_limit
from utils.storage import generate_random_suffix, get_image_url, update_exif_datetime, fix_video_metadata, \
    find_review_dir_by_filename

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

            pc = PIL.Image.open(ori)
            pc.save(ori, quality=70, optimize=True)
            pc.close()

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
            merged = resize_image_limit(merged, max_w=1080, max_h=1920)
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

        # 原文件名
        original_filename = secure_filename(file.filename)
        suffix = os.path.splitext(original_filename)[1].lower()

        # 缓存目录
        cache_dir = "/tmp/upload_cache"
        os.makedirs(cache_dir, exist_ok=True)

        # 生成唯一文件名
        unique_name = f"{uuid4().hex}_{original_filename}"
        tmp_path = os.path.join(cache_dir, unique_name)

        # 保存文件
        file.save(tmp_path)

        # 修改图片 EXIF
        if suffix in ['.jpg', '.jpeg']:
            update_exif_datetime(tmp_path)

        # 修改视频 metadata（创建时间 + 修改时间）
        # elif suffix in ['.mp4', '.mov', '.mkv', '.avi']:
        #     fixed_path = tmp_path + "_fixed" + suffix
        #     fix_video_metadata(tmp_path, fixed_path)
        #
        #     # 用修改后的覆盖
        #     os.remove(tmp_path)
        #     tmp_path = fixed_path

        immich_api = IMMICHApi()
        asset_id = immich_api.upload_to_immich_file(tmp_path)

        # 清理缓存
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass

        UploadRecord.create(
            oss_url='oss_url',
            file_size=100,
            upload_time=datetime.now(),
            etag=etag,
            width=500,
            height=500,
        )

        if not asset_id:
            return jsonify({"success": False, "error": "文件保存失败"}), 500

        return jsonify({"success": True, "asset_id": asset_id, "message": "文件保存成功"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/api/add-review", methods=["POST"])
def add_review():
    """
    保存 review 文件到 storage/reviews/pending/ 目录中，目录结构完整复刻 file_path，
    审核文件名来自上传的 file.filename。

    示例：
    file.filename = 123.jpg
    file_path = /aaa/bbb/ccc/this_is_a_video.mp4

    实际保存路径：
    storage/reviews/pending/aaa/bbb/ccc/this_is_a_video.mp4/123.jpg

    :param file: 上传的文件对象
    :param file_path: 原始业务文件路径，例如 /aaa/bbb/ccc/this_is_a_video.mp4
    :returns: JSON，包含保存路径、相对路径以及原始 file_path 信息
    :raises keyError: 当缺少 file 或 file_path 参数时抛出 KeyError
    """
    file = request.files.get("file")
    file_path = request.form.get("file_path")

    if not file or not file_path:
        raise KeyError("file 和 file_path 为必填参数")

    # 去掉开头的 "/"，并统一为 Unix 风格路径
    clean_path = file_path.lstrip("/").replace("\\", "/")
    # 目录使用完整的 file_path（含原始文件名）
    # storage/reviews/pending/aaa/bbb/ccc/this_is_a_video.mp4/
    save_dir = os.path.join("storage", "reviews", "pending", clean_path)
    os.makedirs(save_dir, exist_ok=True)

    # 审核文件名使用上传文件自身的文件名（一般是 md5 命名的唯一名）
    filename = file.filename or "unnamed.bin"
    save_path = os.path.join(save_dir, filename)

    file.save(save_path)

    # 相对路径用于前端访问 /api/image/reviews/<relative>
    relative_path = f"pending/{clean_path}/{filename}".replace("\\", "/")

    return jsonify({
        "msg": "ok",
        "saved_as": save_path,
        "relative": relative_path,
        "file_path": file_path,
        "filename": filename
    })


@bp.route("/api/review/approve", methods=["POST"])
def review_approve():
    """
    审核通过：根据文件名找到所在目录并整体移动到 approve 下

    :param filename: 文件名（唯一 MD5 名）
    :returns: JSON：移动结果
    """
    filename = request.json.get("filename")
    if not filename:
        raise KeyError("filename 必填")

    try:
        src_dir = find_review_dir_by_filename(filename)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    # pending/.../xxx
    rel_path = os.path.relpath(src_dir, os.path.join("storage", "reviews", "pending"))
    dst_dir = os.path.join("storage", "reviews", "approve", rel_path)

    os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
    shutil.move(src_dir, dst_dir)

    return jsonify({
        "msg": "ok",
        "action": "approve",
        "from": f"pending/{rel_path}",
        "to": f"approve/{rel_path}"
    })


@bp.route("/api/review/reject", methods=["POST"])
def review_reject():
    """
    审核拒绝：根据文件名找到所在目录并整体移动到 reject 下
    """
    filename = request.json.get("filename")
    if not filename:
        raise KeyError("filename 必填")

    try:
        src_dir = find_review_dir_by_filename(filename)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    rel_path = os.path.relpath(src_dir, os.path.join("storage", "reviews", "pending"))
    dst_dir = os.path.join("storage", "reviews", "reject", rel_path)

    os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
    shutil.move(src_dir, dst_dir)

    return jsonify({
        "msg": "ok",
        "action": "reject",
        "from": f"pending/{rel_path}",
        "to": f"reject/{rel_path}"
    })


@bp.route("/api/review/pending-list", methods=["GET"])
def review_pending_list():
    """
    列出所有待审核的文件。

    目录结构示例：
    storage/reviews/pending/aaa/bbb/ccc/this_is_a_video.mp4/123.jpg

    其中：
    - 原始业务 file_path = /aaa/bbb/ccc/this_is_a_video.mp4
    - 审核文件名 = 123.jpg

    :returns: JSON，list 中每一项包含 filename、file_path、dir、relative_path 等字段
    :raises keyError: 本函数不主动抛出 KeyError，占位以统一文档格式
    """
    base_dir = os.path.join("storage", "reviews", "pending")
    results = []

    if not os.path.exists(base_dir):
        return jsonify({"list": []})

    for root, dirs, files in os.walk(base_dir):
        for filename in files:
            # 文件绝对路径
            abs_path = os.path.join(root, filename)
            # 相对于 pending 根目录的路径，例如：
            # "aaa/bbb/ccc/this_is_a_video.mp4/123.jpg"
            rel_path = os.path.relpath(abs_path, base_dir)
            rel_path_unix = rel_path.replace("\\", "/")

            # 目录部分即为原始 file_path（去掉审核文件名）
            # "aaa/bbb/ccc/this_is_a_video.mp4"
            rel_dir_unix = os.path.dirname(rel_path_unix)

            # 原始业务路径（带前导 /）
            file_path = "/" + rel_dir_unix if rel_dir_unix else "/"

            results.append({
                "filename": filename,  # 审核文件名，例如 123.jpg（md5命名）
                "file_path": file_path,  # 原始业务路径，例如 /aaa/bbb/ccc/this_is_a_video.mp4
                "dir": rel_dir_unix,  # 相对于 pending 的目录
                "relative_path": f"pending/{rel_path_unix}"  # 用于 /api/image/reviews/relative_path
            })

    return jsonify({"list": results})


@bp.route("/api/review/approve-list", methods=["GET"])
def review_approve_list():
    """
    获取所有审核通过的业务路径（file_path）

    approve 结构示例：
    storage/reviews/approve/aaa/bbb/ccc/this_is_a_video.mp4/123.jpg

    业务路径 = /aaa/bbb/ccc/this_is_a_video.mp4

    :returns: JSON -> {list: [file_path1, file_path2, ...]}
    :raises keyError: 本接口不抛出 KeyError，用于格式统一
    """
    base_dir = os.path.join("storage", "reviews", "approve")
    results = set()  # 去重

    if not os.path.exists(base_dir):
        return jsonify({"list": []})

    for root, dirs, files in os.walk(base_dir):
        for filename in files:
            # 绝对路径
            abs_path = os.path.join(root, filename)

            # 相对路径：aaa/bbb/ccc/this_is_a_video.mp4/123.jpg
            rel_path = os.path.relpath(abs_path, base_dir)
            rel_path_unix = rel_path.replace("\\", "/")

            # 目录部分即 file_path：aaa/bbb/ccc/this_is_a_video.mp4
            dir_part = os.path.dirname(rel_path_unix)

            if dir_part:
                file_path = "/" + dir_part  # 加前导 /
                results.add(file_path)

    return jsonify({"list": sorted(results)})


@bp.route("/api/review/clear", methods=["POST"])
def review_clear():
    """
    清除审核通过后的业务路径对应目录。
    前端传入 file_path（例如：/storage/emulated/0/Movies/video.mp4）
    后端删除：
        storage/reviews/approve/<file_path去掉前导/>/

    即使路径不存在也返回成功。

    :param file_path: 原业务路径
    :returns: {"msg": "ok"}
    """
    file_path = request.json.get("file_path")

    if not file_path:
        raise KeyError("file_path 必填，如 /storage/emulated/0/Movies/video.mp4")

    # 清洗路径
    clean_path = file_path.lstrip("/").replace("\\", "/")

    # 目标目录
    target_dir = os.path.join("storage", "reviews", "approve", clean_path)

    try:
        # 即使不存在也要“尝试删除”
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

    except Exception as e:
        # 不抛错，只记录，仍返回成功
        log_line(f"[review_clear] 删除失败: {target_dir} -> {e}")

    return jsonify({"msg": "ok"})


@bp.route("/review")
def review_page():
    return render_template("review.html")
