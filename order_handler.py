import json
import logging
import os
import random
import re
import tempfile
import uuid
from typing import Optional, Literal, List

from config import TZ
from order_template import *
from oss_client import get_random_template_url_from_db, download_temp_image
from tasks.watermark_task import add_watermark_to_image
from utils.custom_raise import *
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
    "四乱二扰日巡检": {
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
    "干粉灭火器月巡检": {
        "template": "MHQ",
        "func": order_template_MHQ,
        "image_count": 1,
    },
    "机动车充电区日巡检工单": {
        "template": "JDCCDQ",
        "func": order_template_JDCCDQ,
        "image_count": 1,
    },
    "非机动车停放处日巡查工单": {
        "template": "FJDCTFC",
        "func": order_template_FJDCTFC,
        "image_count": 4,
    },
    "围墙周界报警日巡检": {
        "template": "WQZJ",
        "func": order_template_WQZJ,
        "image_count": 3,
    },
    "空置房巡查月巡检": {
        "template": "KZF",
        "func": order_template_KZF,
        "image_count": 4,
    },
}


def init_template_pic_dirs(user_number: str, base_dir: str = "TemplatePic") -> None:
    """
    根据 ORDER_RULES 在 base_dir 下为指定用户创建目录结构。

    :param user_number: 用户编号，例如 "332211"
    :param base_dir: 根目录名，默认 "TemplatePic"
    """
    # 根目录，例如 TemplatePic
    base_path = os.path.join(base_dir)
    # 用户目录，例如 TemplatePic/332211
    user_path = os.path.join(base_path, user_number)

    # 先保证用户目录存在
    os.makedirs(user_path, exist_ok=True)

    # 遍历 ORDER_RULES 中的每一条规则
    for rule in ORDER_RULES.values():
        template_name = rule["template"]
        image_count = rule["image_count"]

        # 模板目录，例如 TemplatePic/332211/XFTD
        template_dir = os.path.join(user_path, template_name)
        os.makedirs(template_dir, exist_ok=True)

        if template_name == "DYL":
            # 创建楼栋文件夹
            for ld in ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A9', 'A10', 'A11', 'A12', 'B1']:
                ld_dir = os.path.join(template_dir, ld)
                os.makedirs(ld_dir, exist_ok=True)

                # 创建编号子目录：1, 2, ..., image_count
                for i in range(1, image_count + 1):
                    image_dir = os.path.join(ld_dir, str(i))
                    os.makedirs(image_dir, exist_ok=True)
        else:
            # 创建编号子目录：1, 2, ..., image_count
            for i in range(1, image_count + 1):
                image_dir = os.path.join(template_dir, str(i))
                os.makedirs(image_dir, exist_ok=True)


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
        按关键字自动完成工单（对外接口）
        """
        return self._complete_order(
            order_list=order_list,
            mode="keyword",
            user=user,
            user_number=user_number,
            keyword=keyword,
            order_id=None,
        )

    def complete_order_by_id(self, order_list, order_id, user: str, user_number: str):
        """
        按工单 ID 自动完成工单（对外接口）
        """
        return self._complete_order(
            order_list=order_list,
            mode="id",
            user=user,
            user_number=user_number,
            keyword=None,
            order_id=order_id,
        )

    def _complete_order(
            self,
            order_list,
            mode: Literal["keyword", "id"],
            user: str,
            user_number: str,
            keyword: Optional[str],
            order_id,
    ):
        """
        统一的工单处理流水线：
        - 根据 mode 决定如何在列表中查找目标工单
        - 根据工单 title 匹配规则
        - 生成带水印图片
        - 启动工单、上传图片、提交工单、发送通知
        """

        # 1️⃣ 创建用户目录
        init_template_pic_dirs(user_number)

        # 2️⃣ 根据 mode 查找目标工单
        if mode == "keyword":
            if not keyword:
                raise ValueError("mode=keyword 时必须提供 keyword 参数")

            target_order = next(
                (o for o in order_list if keyword in o.get("title", "")),
                None,
            )
            if not target_order:
                msg = f"未找到包含关键字【{keyword}】的工单"
                logger.warning(msg)
                raise OrderNotFoundError(msg)

            search_desc = f"keyword={keyword}"
            mode_desc = "按关键字"
            log_prefix = "[按关键字]"
            notify_suffix = "（按关键字触发）"

        elif mode == "id":
            if order_id is None:
                raise ValueError("mode=id 时必须提供 order_id 参数")

            target_order = next(
                (o for o in order_list if str(o.get("id")) == str(order_id)),
                None,
            )
            if not target_order:
                msg = f"未在工单列表中找到 ID 为【{order_id}】的工单"
                logger.warning(msg)
                raise OrderNotFoundError(msg)

            search_desc = f"order_id={order_id}"
            mode_desc = "按工单ID"
            log_prefix = "[按工单ID]"
            notify_suffix = "（按工单ID触发）"

        else:
            raise ValueError(f"不支持的 mode: {mode!r}")

        # 3️⃣ 解析工单基础信息
        title = target_order["title"]
        status = target_order["status"]
        order_id = target_order["id"]  # 用列表里的真实值覆盖一下

        # 4️⃣ 查找工单规则
        rule = None
        for key in ORDER_RULES:
            if key in title:
                rule = ORDER_RULES[key]

        if not rule:
            msg = f"未找到工单【{title}】对应的规则，无法处理"
            logger.warning(msg)
            raise RuleNotFoundError(msg)

        logger.info(
            f"{mode_desc}完成工单: {title}[{order_id}], "
            f"{search_desc}, user={user}, user_number={user_number}"
        )

        # 5️⃣ 启动工单
        if status == "3":
            self.fm.start_order(order_id)

        # 6️⃣ 获取图片数量 + 预生成每一张的水印时间
        image_count = rule["image_count"]

        # watermark_times[i] 对应第 i 张图的时间
        watermark_times: List[datetime.datetime] = [None] * image_count  # type: ignore
        current_dt = datetime.datetime.now(TZ)

        # 从最后一张往前推：
        # - 最后一张 = now
        # - 每往前一张，在上一张基础上随机减 1~2 分钟
        for idx in reversed(range(image_count)):
            watermark_times[idx] = current_dt
            if idx > 0:
                offset_minutes = random.randint(1, 2)
                current_dt -= datetime.timedelta(minutes=offset_minutes)

        logger.debug(
            f"{log_prefix} 生成水印时间序列: "
            + ", ".join(dt.strftime("%Y-%m-%d %H:%M") for dt in watermark_times)
        )

        # 7️⃣ 生成水印图片（唯一文件名），每张使用各自的 base_date/base_time
        image_paths: List[str] = []
        downloaded_templates: List[str] = []  # 记录下载到本地的模板路径，用于后续清理

        try:
            for i in range(image_count):
                # 1. 确定分类和子分类逻辑
                category = rule['template']
                sub_category = ""
                sequence = str(i + 1)

                if title == "单元楼栋月巡检":
                    matches = re.findall(r"[a-zA-Z]\d+", target_order.get("address", ""))
                    if matches:
                        sub_category = matches[0]

                # 2. 从数据库获取随机 URL
                cos_url = get_random_template_url_from_db(user_number, category, sub_category, sequence)

                # 3. 下载模板到本地临时目录
                if cos_url:
                    original_image_path = download_temp_image(cos_url, self.tmp_dir)
                else:
                    # Fallback 逻辑：如果数据库没有，使用本地的 black.jpg
                    original_image_path = "black.jpg"
                    # 注意：如果是 black.jpg，不需要放进待删除列表，除非它是动态生成的

                if not original_image_path or not os.path.exists(original_image_path):
                    msg = f"无法获取模板图片: {category}/{sub_category}/{sequence}"
                    logger.error(msg)
                    raise ImageUploadError(msg)

                # 记录下载的路径，任务结束后删除
                if original_image_path != "black.jpg":
                    downloaded_templates.append(original_image_path)

                # 使用为当前索引预先计算好的水印时间
                wm_dt = watermark_times[i]
                base_date = wm_dt.strftime("%Y-%m-%d")
                base_time = wm_dt.strftime("%H:%M")

                # 输出临时文件名
                tmp_filename = f"wm_{uuid.uuid4().hex}.jpg"
                tmp_path = os.path.join(self.tmp_dir, tmp_filename)

                # 生成水印图片
                add_watermark_to_image(
                    original_image_path=original_image_path,
                    base_date=base_date,
                    base_time=base_time,
                    name=user,
                    user_number=user_number,
                    output_path=tmp_path,
                )
                image_paths.append(tmp_path)
        finally:
            # --- 最终统一清理 ---
            # 1. 清理下载的模板原图
            for path in downloaded_templates:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    logger.error(f"清理模板缓存失败: {path}, {e}")

        # 8️⃣ 上传图片（任意一张失败直接抛错）
        uploaded_urls: List[str] = []
        try:
            for path in image_paths:
                url = self.oss.upload(path)
                uploaded_urls.append(url)
                logger.info(f"{log_prefix} 上传成功: {url}")
        except Exception as e:
            msg = f"{log_prefix} 上传失败: {e}"
            logger.error(msg, exc_info=True)
            # 清理已生成的临时文件再抛异常
            for p in image_paths:
                try:
                    os.remove(p)
                except Exception:
                    pass
            raise ImageUploadError(msg) from e
        finally:
            # 9️⃣ 清理临时文件（失败不视为致命错误）
            for path in image_paths:
                try:
                    os.remove(path)
                    logger.debug(f"{log_prefix} 已删除临时文件: {path}")
                except Exception as e:
                    logger.warning(f"{log_prefix} 删除临时文件失败: {path}, {e}")

        # 🔟 校验上传数量
        if len(uploaded_urls) < image_count:
            msg = (
                f"{log_prefix} 部分图片上传失败，未提交工单: "
                f"{len(uploaded_urls)}/{image_count}"
            )
            logger.warning(msg)
            raise PartialUploadError(msg)

        # 1️⃣1️⃣ 提交工单
        payload = rule["func"](order_id, *uploaded_urls)
        self.fm.submit_order(payload)
        logger.info(f"{log_prefix} 提交工单: {json.dumps(payload, ensure_ascii=False)}")
        self.notify.send(f"工单【{title}】已完成{notify_suffix}")

        logger.info(f"工单【{title}】{mode_desc}处理完成 ✅")

        # 1️⃣2️⃣ 返回信息（按原来两个方法的差异来拼）
        result = {
            "order_id": order_id,
            "title": title,
            "user": user,
            "user_number": user_number,
            "upload_count": len(uploaded_urls),
        }
        if mode == "keyword":
            result["keyword"] = keyword
        return result
