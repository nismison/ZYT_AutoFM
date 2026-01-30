import json
import time
import concurrent.futures
from datetime import datetime

from config import TZ
from db import CompleteTask

from apis.fm_api import FMApi
from oss_client import OSSClient
from order_handler import OrderHandler


def complete_task_worker():
    """
    后台异步任务：
    - /api/fm/complete_task 写入 CompleteTask
    - worker 轮询 pending 任务
    - 抢占成功后执行 complete_order_by_keyword / complete_order_by_id
    - 成功写 result_json 并置 done
    - 失败写 error 并置 failed
    """

    print("[INFO] FM complete 队列后台任务已启动")

    while True:
        task = None

        try:
            # 取一条 pending 任务
            task = (
                CompleteTask
                .select()
                .where(CompleteTask.status == "pending")
                .order_by(CompleteTask.created_at.asc())
                .first()
            )

            if not task:
                time.sleep(0.2)
                continue

            # 抢占任务
            rows = (
                CompleteTask
                .update(status="processing", updated_at=datetime.now(TZ))
                .where(CompleteTask.id == task.id, CompleteTask.status == "pending")
                .execute()
            )
            if rows == 0:
                continue

            print(
                f"[INFO] 开始处理任务: id={task.id}, mode={task.mode}, order_id={task.order_id}, keyword={task.keyword}"
            )

            # 解析 template_pics_json
            try:
                template_pics = json.loads(task.template_pics_json or "[]")
                if not isinstance(template_pics, list):
                    template_pics = []
            except Exception:
                template_pics = []

            # 定义执行逻辑
            def run_task():
                fm = FMApi()
                oss = OSSClient(fm.session, fm.token)
                handler = OrderHandler(fm, oss)

                records = fm.get_need_deal_list()

                if task.mode == "keyword":
                    if not task.keyword:
                        raise RuntimeError("任务缺少 keyword")
                    return handler.complete_order_by_keyword(
                        records,
                        task.keyword,
                        task.user_name,
                        task.user_number,
                        template_pics,
                    )
                elif task.mode == "id":
                    if not task.order_id:
                        raise RuntimeError("任务缺少 order_id")
                    return handler.complete_order_by_id(
                        records,
                        task.order_id,
                        task.user_name,
                        task.user_number,
                        template_pics,
                    )
                else:
                    raise RuntimeError(f"未知任务 mode: {task.mode}")

            # 使用线程池执行并设置超时
            timeout_seconds = 120  # 2分钟超时
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_task)
                    result = future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                raise RuntimeError(f"任务执行超时（超过 {timeout_seconds} 秒）")

            # 标记任务完成
            (
                CompleteTask
                .update(
                    status="done",
                    result_json=json.dumps(result, ensure_ascii=False),
                    error=None,
                    updated_at=datetime.now(TZ),
                )
                .where(CompleteTask.id == task.id)
                .execute()
            )

            print(f"[INFO] 任务完成: id={task.id}")
            continue

        except Exception as e:
            print(f"[ERROR] 任务执行失败: {e}")

            if task is not None:
                (
                    CompleteTask
                    .update(
                        status="failed",
                        error=str(e),
                        updated_at=datetime.now(TZ),
                    )
                    .where(CompleteTask.id == task.id)
                    .execute()
                )

        time.sleep(0.1)


if __name__ == "__main__":
    complete_task_worker()
