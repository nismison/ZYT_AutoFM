# utils/pool.py
from concurrent.futures import ProcessPoolExecutor

# 根据 CPU 核数建议设置 max_workers
WATERMARK_POOL = ProcessPoolExecutor(max_workers=3)


def watermark_task(args):
    """
    子进程执行的水印任务（不依赖 Flask，不依赖 app）
    """
    (ori_path,
     name,
     user_number,
     base_date,
     base_time,
     output_path,
     minute_offset,
    ) = args

    from utils.generate_water_mark import add_watermark_to_image

    return add_watermark_to_image(
        original_image_path=ori_path,
        name=name,
        user_number=user_number,
        base_date=base_date,
        base_time=base_time,
        output_path=output_path,
        minute_offset=minute_offset
    )
