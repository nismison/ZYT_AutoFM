import datetime
import json
import logging
import os
import re
import tempfile
import uuid

from order_template import order_template_XFTD, order_template_4L2R, order_template_GGQY, order_template_5S, \
    order_template_QC, order_template_XFSS, order_template_DYL, order_template_TTFX
from tasks.watermark_task import add_watermark_to_image
from utils.custom_raise import OrderNotFoundError, RuleNotFoundError, ImageUploadError, \
    PartialUploadError
from utils.notification import Notify
from utils.storage import get_random_template_file

logger = logging.getLogger(__name__)


def generate_default_times(base_hour, ranges):
    """通用时间生成器"""
    return [(base_hour, r) for r in ranges]


def remove_duplicate_titles(order_list):
    """
    去除列表中title重复的项，只保留每个title第一次出现的项

    参数:
        order_list: 包含字典的列表，每个字典需要有 'title' 键

    返回:
        去重后的列表
    """
    seen_titles = set()
    unique_orders = []

    for order in order_list:
        title = order.get('title')
        if title not in seen_titles:
            seen_titles.add(title)
            unique_orders.append(order)

    return unique_orders


# 上午 -> 11:30 执行
# 消防通道门日巡查 -> 10:10 ~ 10:15
# 消防设施月巡检 -> 10:16 ~ 10:27
# 四乱二扰日巡检（白） -> 10:28 ~ 10:33
# 公共区域风险隐患排查日巡检工单 -> 10:34 ~ 10:39
# 门岗BI&5S日巡检 -> 10:40 ~ 10:45
# 外来人员清场日巡查工单 -> 10:46 ~ 10:48
# 单元楼栋月巡检 -> 10:49 ~ 10:57
# 天台风险月巡查 -> 11:10 ~ 10:18

# 下午 -> 16:00 执行
# 消防通道门日巡查 -> 14:10 ~ 14:15
# 消防设施月巡检 -> 14:16 ~ 14:27
# 单元楼栋月巡检 -> 14:28 ~ 14:36
# 天台风险月巡查 -> 14:37 ~ 14:46

# ====== 工单模板配置 ======
ORDER_RULES = {
    "消防通道门日巡查": {
        "template": "XFTD",
        "func": order_template_XFTD,
        "image_count": 2,
    },
    "消防设施月巡检": {
        "template": "XFSS",
        "func": order_template_XFSS,
        "image_count": 4,
    },
    "四乱二扰日巡检（白）": {
        "template": "4L2R",
        "func": order_template_4L2R,
        "image_count": 2
    },
    "公共区域风险隐患排查日巡检工单": {
        "template": "GGQY",
        "func": order_template_GGQY,
        "image_count": 2
    },
    "门岗BI&5S日巡检": {
        "template": "5S",
        "func": order_template_5S,
        "image_count": 2
    },
    "外来人员清场日巡查工单": {
        "template": "QC",
        "func": order_template_QC,
        "image_count": 1
    },
    "单元楼栋月巡检": {
        "template": "DYL",
        "func": order_template_DYL,
        "image_count": 3,
    },
    "天台风险月巡查": {
        "template": "TTFX",
        "func": order_template_TTFX,
        "image_count": 3,
    },
}


class OrderHandler:
    def __init__(self, fm, oss):
        self.fm = fm
        self.oss = oss
        self.notify = Notify()

        # 设置统一临时目录
        self.tmp_dir = os.path.join(tempfile.gettempdir(), "order_watermarks")
        os.makedirs(self.tmp_dir, exist_ok=True)

    def complete_order_by_keyword(self, order_list, keyword: str, user: str, user_number: str):
        """
        完成指定工单：
        - 在去重后的工单列表中查找 title 包含 keyword 的工单（取第一个）
        - 使用当前日期/时间生成水印，并传入 name 和 user_number
        - 启动工单、上传图片、提交工单、发送通知

        成功：返回一个包含基本信息的 dict
        失败：抛出 OrderHandlerError 子类异常，供上层接口捕获并返回给前端
        """

        # 0️⃣ 去重
        unique_order_list = remove_duplicate_titles(order_list)

        # 1️⃣ 查找包含 keyword 的工单（按 title 匹配，取第一个）
        target_order = next(
            (o for o in unique_order_list if keyword in o.get("title", "")),
            None,
        )
        if not target_order:
            msg = f"未找到包含关键字【{keyword}】的工单"
            logger.warning(msg)
            raise OrderNotFoundError(msg)

        title = target_order["title"]
        order_id = target_order["id"]
        status = target_order["status"]

        # 2️⃣ 获取规则
        rule = ORDER_RULES.get(title)
        if not rule:
            msg = f"未找到工单【{title}】对应的规则，无法处理"
            logger.warning(msg)
            raise RuleNotFoundError(msg)

        logger.info(
            f"按关键字完成工单: {title}[{order_id}], "
            f"keyword={keyword}, user={user}, user_number={user_number}"
        )

        # 4️⃣ 启动工单（与 _process_order 保持一致）
        if status == "3":
            self.fm.start_order(order_id)

        # 5️⃣ 获取图片数量
        image_count = rule["image_count"]

        # 固定日期 / 时间：今天 + 当前时间
        now = datetime.datetime.now()
        base_date = now.strftime("%Y-%m-%d")
        base_time = now.strftime("%H:%M")

        # 6️⃣ 生成水印图片（唯一文件名），但时间固定为当前
        image_paths = []
        for i in range(image_count):
            tmp_filename = f"wm_{uuid.uuid4().hex}.jpg"
            tmp_path = os.path.join(self.tmp_dir, tmp_filename)

            template_path = rule["template"]
            if title == "单元楼栋月巡检":
                # 如果订单包含位置信息，则使用位置子目录
                matches = re.findall(r"[a-zA-Z]\d+", target_order.get("address", ""))
                if matches:
                    template_path = f"{rule['template']}/{matches[0]}"

            add_watermark_to_image(
                original_image_path=get_random_template_file(template_path, str(i + 1)),
                base_date=base_date,
                base_time=base_time,
                name=user,
                user_number=user_number,
                output_path=tmp_path,
            )
            image_paths.append(tmp_path)

        # 7️⃣ 上传图片（任意一张失败直接抛错）
        uploaded_urls = []
        for path in image_paths:
            try:
                url = self.oss.upload(path)
                uploaded_urls.append(url)
                logger.info(f"[按关键字] 上传成功: {url}")
            except Exception as e:
                msg = f"[按关键字] 上传失败: {e}"
                logger.error(msg, exc_info=True)
                # 清理已生成的临时文件再抛异常
                for p in image_paths:
                    try:
                        os.remove(p)
                    except Exception:
                        pass
                raise ImageUploadError(msg) from e

        # 8️⃣ 清理临时文件
        for path in image_paths:
            try:
                os.remove(path)
                logger.debug(f"[按关键字] 已删除临时文件: {path}")
            except Exception as e:
                # 清理失败不视为致命错误，打个 warning 即可
                logger.warning(f"[按关键字] 删除临时文件失败: {path}, {e}")

        # 9️⃣ 提交工单
        if len(uploaded_urls) < image_count:
            msg = (
                f"[按关键字] 部分图片上传失败，未提交工单: "
                f"{len(uploaded_urls)}/{image_count}"
            )
            logger.warning(msg)
            raise PartialUploadError(msg)

        payload = rule["func"](order_id, *uploaded_urls)
        self.fm.submit_order(payload)
        logger.info(f"[按关键字] 提交工单: {json.dumps(payload, ensure_ascii=False)}")
        self.notify.send(f"工单【{title}】已完成（按关键字触发）")

        logger.info(f"工单【{title}】按关键字处理完成 ✅")

        # 返回一些信息，方便接口直接用
        return {
            "order_id": order_id,
            "title": title,
            "keyword": keyword,
            "user": user,
            "user_number": user_number,
            "upload_count": len(uploaded_urls),
        }

    def complete_order_by_id(self, order_list, order_id, user: str, user_number: str):
        """
        根据工单 ID 自动完成工单：
        - 在去重后的工单列表中查找 id 匹配的工单（取第一个）
        - 根据工单 title 匹配规则
        - 使用当前日期/时间生成水印，并传入 name 和 user_number
        - 启动工单、上传图片、提交工单、发送通知

        成功：返回一个包含基本信息的 dict
        失败：抛出 OrderHandlerError 子类异常，供上层接口捕获并返回给前端
        """

        # 0️⃣ 去重（按 title 去重的规则保持一致）
        unique_order_list = remove_duplicate_titles(order_list)

        # 1️⃣ 查找 id 匹配的工单（注意把两边都转成 str，避免 int/str 混用匹配失败）
        target_order = next(
            (o for o in unique_order_list if str(o.get("id")) == str(order_id)),
            None,
        )
        if not target_order:
            msg = f"未在工单列表中找到 ID 为【{order_id}】的工单"
            logger.warning(msg)
            raise OrderNotFoundError(msg)

        title = target_order["title"]
        status = target_order["status"]
        order_id = target_order["id"]  # 用列表里的真实值覆盖一下，避免类型不一致

        # 2️⃣ 获取规则
        rule = ORDER_RULES.get(title)
        if not rule:
            msg = f"未找到工单【{title}】对应的规则，无法处理"
            logger.warning(msg)
            raise RuleNotFoundError(msg)

        logger.info(
            f"按工单ID完成工单: {title}[{order_id}], "
            f"user={user}, user_number={user_number}"
        )

        # 4️⃣ 启动工单（与 _process_order / complete_order_by_keyword 保持一致）
        if status == "3":
            self.fm.start_order(order_id)

        # 5️⃣ 获取图片数量
        image_count = rule["image_count"]

        # 固定日期 / 时间：今天 + 当前时间
        now = datetime.datetime.now()
        base_date = now.strftime("%Y-%m-%d")
        base_time = now.strftime("%H:%M")

        # 6️⃣ 生成水印图片（唯一文件名），但时间固定为当前
        image_paths = []
        for i in range(image_count):
            tmp_filename = f"wm_{uuid.uuid4().hex}.jpg"
            tmp_path = os.path.join(self.tmp_dir, tmp_filename)

            template_path = rule["template"]
            if title == "单元楼栋月巡检":
                # 如果订单包含位置信息，则使用位置子目录
                matches = re.findall(r"[a-zA-Z]\d+", target_order.get("address", ""))
                if matches:
                    template_path = f"{user_number}/{rule['template']}/{matches[0]}"

            add_watermark_to_image(
                original_image_path=get_random_template_file(template_path, str(i + 1)),
                base_date=base_date,
                base_time=base_time,
                name=user,
                user_number=user_number,
                output_path=tmp_path,
            )
            image_paths.append(tmp_path)

        # 7️⃣ 上传图片（任意一张失败直接抛错）
        uploaded_urls = []
        for path in image_paths:
            try:
                url = self.oss.upload(path)
                uploaded_urls.append(url)
                logger.info(f"[按工单ID] 上传成功: {url}")
            except Exception as e:
                msg = f"[按工单ID] 上传失败: {e}"
                logger.error(msg, exc_info=True)
                # 清理已生成的临时文件再抛异常
                for p in image_paths:
                    try:
                        os.remove(p)
                    except Exception:
                        pass
                raise ImageUploadError(msg) from e

        # 8️⃣ 清理临时文件
        for path in image_paths:
            try:
                os.remove(path)
                logger.debug(f"[按工单ID] 已删除临时文件: {path}")
            except Exception as e:
                # 清理失败不视为致命错误，打个 warning 即可
                logger.warning(f"[按工单ID] 删除临时文件失败: {path}, {e}")

        # 9️⃣ 提交工单
        if len(uploaded_urls) < image_count:
            msg = (
                f"[按工单ID] 部分图片上传失败，未提交工单: "
                f"{len(uploaded_urls)}/{image_count}"
            )
            logger.warning(msg)
            raise PartialUploadError(msg)

        payload = rule["func"](order_id, *uploaded_urls)
        self.fm.submit_order(payload)
        logger.info(f"[按工单ID] 提交工单: {json.dumps(payload, ensure_ascii=False)}")
        self.notify.send(f"工单【{title}】已完成（按工单ID触发）")

        logger.info(f"工单【{title}】按工单ID处理完成 ✅")

        # 返回一些信息，方便上层接口直接用
        return {
            "order_id": order_id,
            "title": title,
            "user": user,
            "user_number": user_number,
            "upload_count": len(uploaded_urls),
        }
