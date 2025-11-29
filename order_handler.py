import datetime
import json
import logging
import os
import random
import re
import tempfile
import uuid

from peewee import DoesNotExist

from apis.fm_api import FMApi
from db import UserInfo
from order_template import order_template_XFTD, order_template_4L2R, order_template_GGQY, order_template_5S, \
    order_template_QC, order_template_XFSS, order_template_DYL, order_template_TTFX
from oss_client import OSSClient
from tasks.watermark_task import add_watermark_to_image
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
        "time_func": lambda: generate_default_times(
            10, [(10, 12), (13, 15)]
        ) if datetime.datetime.now().hour < 12 else generate_default_times(
            14, [(10, 12), (13, 15)]
        )
    },
    "消防设施月巡检": {
        "template": "XFSS",
        "func": order_template_XFSS,
        "image_count": 4,
        "time_func": lambda: generate_default_times(
            10, [(16, 18), (19, 21), (22, 24), (25, 27)]
        ) if datetime.datetime.now().hour < 12 else generate_default_times(
            14, [(16, 18), (19, 21), (22, 24), (25, 27)]
        )
    },
    "四乱二扰日巡检（白）": {
        "template": "4L2R",
        "times": generate_default_times(10, [(28, 30), (31, 33)]),
        "func": order_template_4L2R,
        "image_count": 2
    },
    "公共区域风险隐患排查日巡检工单": {
        "template": "GGQY",
        "times": generate_default_times(10, [(34, 36), (37, 39)]),
        "func": order_template_GGQY,
        "image_count": 2
    },
    "门岗BI&5S日巡检": {
        "template": "5S",
        "times": generate_default_times(10, [(40, 42), (43, 45)]),
        "func": order_template_5S,
        "image_count": 2
    },
    "外来人员清场日巡查工单": {
        "template": "QC",
        "times": generate_default_times(10, [(46, 48)]),
        "func": order_template_QC,
        "image_count": 1
    },
    "单元楼栋月巡检": {
        "template": "DYL",
        "func": order_template_DYL,
        "image_count": 3,
        "time_func": lambda: generate_default_times(
            10, [(49, 51), (52, 54), (55, 57)]
        ) if datetime.datetime.now().hour < 12 else generate_default_times(
            14, [(28, 30), (31, 33), (34, 36)]
        )
    },
    "天台风险月巡查": {
        "template": "TTFX",
        "func": order_template_TTFX,
        "image_count": 3,
        "time_func": lambda: generate_default_times(
            11, [(10, 12), (13, 15), (16, 18)]
        ) if datetime.datetime.now().hour < 12 else generate_default_times(
            14, [(37, 39), (41, 43), (44, 46)]
        )
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

    def handle_all_orders(self, order_list):
        unique_order_list = remove_duplicate_titles(order_list)

        for order in unique_order_list:
            rule = ORDER_RULES.get(order['title'])
            if not rule:
                continue
            self._process_order(order, rule)

    def _process_order(self, order, rule):
        status = order['status']
        order_id = order['id']
        title = order['title']
        logger.info(f"开始处理工单: {title}[{order_id}]")

        # 1️⃣ 启动工单（只有状态为 3-已接受 才执行启动工单）
        status == '3' and self.fm.start_order(order_id)

        # 2️⃣ 获取动态时间表
        times = rule['time_func']() if 'time_func' in rule else rule['times']

        # 3️⃣ 生成水印图片（唯一文件名）
        image_paths = []
        for i, (hour, (m1, m2)) in enumerate(times):
            minute = random.randint(m1, m2)

            # 随机生成唯一缓存文件路径
            tmp_filename = f"wm_{uuid.uuid4().hex}.jpg"
            tmp_path = os.path.join(self.tmp_dir, tmp_filename)

            template_path = rule['template']

            if order['title'] == "单元楼栋月巡检":
                # 如果订单包含位置信息，则使用位置子目录
                matches = re.findall(r'[a-zA-Z]\d+', order["address"])
                template_path = f"{rule['template']}/{matches[0]}"

            # 执行水印生成
            add_watermark_to_image(
                original_image_path=get_random_template_file(template_path, str(i + 1)),
                base_time=f"{hour}:{minute}",
                output_path=tmp_path
            )
            image_paths.append(tmp_path)

        # 4️⃣ 上传图片
        uploaded_urls = []
        for path in image_paths:
            try:
                url = self.oss.upload(path)
                uploaded_urls.append(url)
                logger.info(f"上传成功: {url}")

            except Exception as e:
                logger.error(f"上传失败: {e}")

        # 5️⃣ 清理临时文件
        for path in image_paths:
            try:
                os.remove(path)
                logger.debug(f"已删除临时文件: {path}")
            except Exception as e:
                logger.warning(f"删除临时文件失败: {path}, {e}")

        # 6️⃣ 构造 payload 并提交
        if len(uploaded_urls) < len(times):
            logger.warning(f"部分图片上传失败，重试: {len(uploaded_urls)}/{len(times)}")
            self._process_order(order, rule)
        else:
            payload = rule['func'](order_id, *uploaded_urls)
            self.fm.submit_order(payload)
            logger.info(f"提交工单: {json.dumps(payload)}")
            self.notify.send(f"工单【{title}】已完成")

            logger.info(f"工单【{title}】处理完成 ✅")

    def complete_order_by_keyword(self, order_list, keyword: str, user: str):
        """
        完成指定工单：
        - 在去重后的工单列表中查找 title 包含 keyword 的工单（取第一个）
        - 使用当前日期/时间生成水印，并传入 name 和 user_number
        - 启动工单、上传图片、提交工单、发送通知
        """

        # 0️⃣ 去重
        unique_order_list = remove_duplicate_titles(order_list)

        # 1️⃣ 查找包含 keyword 的工单（按 title 匹配，取第一个）
        target_order = next(
            (o for o in unique_order_list if keyword in o.get("title", "")),
            None,
        )
        if not target_order:
            logger.warning(f"未找到包含关键字【{keyword}】的工单")
            return

        title = target_order["title"]
        order_id = target_order["id"]
        status = target_order["status"]

        # 2️⃣ 获取规则
        rule = ORDER_RULES.get(title)
        if not rule:
            logger.warning(f"未找到工单【{title}】对应的规则，无法处理")
            return

        # 3️⃣ 获取用户信息 → user_number
        try:
            user_info = UserInfo.get(UserInfo.name == user)
        except DoesNotExist:
            logger.error(f"未找到用户【{user}】的用户信息记录，无法生成水印")
            return

        logger.info(
            f"按关键字完成工单: {title}[{order_id}], "
            f"keyword={keyword}, user={user}, user_number={user_info.user_number}"
        )

        # 4️⃣ 启动工单（与 _process_order 保持一致）
        status == "3" and self.fm.start_order(order_id)

        # 5️⃣ 获取时间配置，只用于决定生成几张图 / 模板序号
        times = rule["time_func"]() if "time_func" in rule else rule["times"]

        # 固定日期 / 时间：今天 + 当前时间
        now = datetime.datetime.now()
        base_date = now.strftime("%Y-%m-%d")
        base_time = now.strftime("%H:%M")

        # 6️⃣ 生成水印图片（唯一文件名），但时间固定为当前
        image_paths = []
        for i, _ in enumerate(times):
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
                user_number=user_info.user_number,
                output_path=tmp_path,
            )
            image_paths.append(tmp_path)

        # 7️⃣ 上传图片
        uploaded_urls = []
        for path in image_paths:
            try:
                url = self.oss.upload(path)
                uploaded_urls.append(url)
                logger.info(f"[按关键字] 上传成功: {url}")
            except Exception as e:
                logger.error(f"[按关键字] 上传失败: {e}")

        # 8️⃣ 清理临时文件
        for path in image_paths:
            try:
                os.remove(path)
                logger.debug(f"[按关键字] 已删除临时文件: {path}")
            except Exception as e:
                logger.warning(f"[按关键字] 删除临时文件失败: {path}, {e}")

        # 9️⃣ 提交工单（这里只简单判断，不做递归重试；需要可以按 _process_order 改成重试）
        if len(uploaded_urls) < len(times):
            logger.warning(
                f"[按关键字] 部分图片上传失败，未提交工单: {len(uploaded_urls)}/{len(times)}"
            )
            return

        payload = rule["func"](order_id, *uploaded_urls)
        self.fm.submit_order(payload)
        logger.info(f"[按关键字] 提交工单: {json.dumps(payload)}")
        self.notify.send(f"工单【{title}】已完成（按关键字触发）")

        logger.info(f"工单【{title}】按关键字处理完成 ✅")

if __name__ == '__main__':
    fm = FMApi()
    oss = OSSClient(fm.session, fm.token)
    handler = OrderHandler(fm, oss)

    logging.info("开始获取待处理工单列表...")
    deal_data = fm.get_need_deal_list()
    records = deal_data.get("records", [])

    if not records:
        logging.info("没有待处理的工单")
    else:
        handler.complete_order_by_keyword(records, "天台风险", "梁振卓")