import datetime
import json
import logging
import os
import random
import tempfile
import uuid

from GenerateWaterMark import add_watermark_to_image
from Notification import Notify
from OrderTemplate import order_template_XFTD, order_template_4L2R, order_template_GGQY, order_template_5S, \
    order_template_QC, order_template_XFSS
from Utils import Utils

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


# ====== 工单模板配置 ======
ORDER_RULES = {
    "消防通道门日巡查": {
        "template": "XFTD",
        "func": order_template_XFTD,
        "image_count": 2,
        # 上午 (<12) → 10:20~10:30，下午 (>=12) → 14:40~14:50
        "time_func": lambda: generate_default_times(
            10, [(20, 25), (25, 30)]
        ) if datetime.datetime.now().hour < 12 else generate_default_times(
            14, [(40, 45), (45, 50)]
        )
    },
    "消防设施月巡检": {
        "template": "XFSS",
        "func": order_template_XFSS,
        "image_count": 4,
        # 上午 (<12) → 11:10~11:22，下午 (>=12) → 14:28~14:40
        "time_func": lambda: generate_default_times(
            11, [(10, 13), (13, 16), (16, 19), (19, 22)]
        ) if datetime.datetime.now().hour < 12 else generate_default_times(
            14, [(28, 31), (31, 34), (34, 37), (37, 40)]
        )
    },
    "四乱二扰日巡检（白）": {
        "template": "4L2R",
        "times": generate_default_times(10, [(10, 15), (15, 20)]),
        "func": order_template_4L2R,
        "image_count": 2
    },
    "公共区域风险隐患排查日巡检工单": {
        "template": "GGQY",
        "times": generate_default_times(10, [(30, 35), (35, 40)]),
        "func": order_template_GGQY,
        "image_count": 2
    },
    "门岗BI&5S日巡检": {
        "template": "5S",
        "times": generate_default_times(10, [(40, 45), (45, 50)]),
        "func": order_template_5S,
        "image_count": 2
    },
    "外来人员清场日巡查工单": {
        "template": "QC",
        "times": generate_default_times(10, [(50, 59)]),
        "func": order_template_QC,
        "image_count": 1
    },
}


class OrderHandler:
    def __init__(self, fm, oss):
        self.fm = fm
        self.oss = oss
        self.utils = Utils()
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

            # 执行水印生成
            add_watermark_to_image(
                original_image_path=self.utils.get_random_template_file(f"{rule['template']}/{i + 1}"),
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
                logger.info(f"上传成功: {path} -> {url}")

            except Exception as e:
                logger.error(f"上传失败: {path}, 错误: {e}")

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
            # logger.info(f"提交工单: {payload}")
            self.notify.send(f"工单【{title}】已完成")

            logger.info(f"工单【{title}】处理完成 ✅")
