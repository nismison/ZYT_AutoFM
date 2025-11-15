import cv2
import numpy as np
from PIL import Image


def merge_images_grid(image_paths,
                            target_width: int = 1500,
                            padding: int = 4,
                            bg_color=(255, 255, 255)) -> Image.Image:
    """
    使用 numpy + OpenCV 进行高性能多图拼接，生成自适应网格布局

    :param image_paths: 图片路径列表
    :param target_width: 最终合成图片宽度
    :param padding: 图片间距像素
    :param bg_color: 背景颜色 (R, G, B)
    :returns: 已合成的 PIL.Image 对象
    :raises keyError: 不涉及字典访问，不会抛出 keyError
    """
    pil_images = [Image.open(p).convert("RGB") for p in image_paths]
    imgs = [np.array(img) for img in pil_images]
    n = len(imgs)
    if n == 0:
        raise ValueError("No images provided")

    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))

    groups = []
    idx = 0
    for _ in range(rows):
        remain = n - idx
        count = min(cols, remain)
        groups.append(imgs[idx: idx + count])
        idx += count

    resized_rows = []
    total_h = 0

    for row_imgs in groups:
        ratios = [img.shape[1] / img.shape[0] for img in row_imgs]
        total_ratio = sum(ratios)
        row_h = int(target_width / total_ratio)

        scaled_row = []
        for img, r in zip(row_imgs, ratios):
            new_w = int(row_h * r)
            resized = cv2.resize(img, (new_w, row_h))
            scaled_row.append(resized)

        row_w = sum(im.shape[1] for im in scaled_row) + padding * (len(scaled_row) - 1)
        row_canvas = np.full((row_h, row_w, 3), bg_color, dtype=np.uint8)

        x = 0
        for im in scaled_row:
            h, w = im.shape[0], im.shape[1]
            row_canvas[0:h, x: x + w] = im
            x += w + padding

        resized_rows.append(row_canvas)
        total_h += row_h + padding

    total_h -= padding
    canvas = np.full((total_h, target_width, 3), bg_color, dtype=np.uint8)

    y = 0
    for row in resized_rows:
        h, w = row.shape[0], row.shape[1]
        if w > target_width:
            row = cv2.resize(row, (target_width, h))
        cw = row.shape[1]
        offset = (target_width - cw) // 2
        canvas[y:y + h, offset:offset + cw] = row
        y += h + padding

    return Image.fromarray(canvas)


def resize_image_limit(img, max_w=1080, max_h=1920):
    """
    限制图片最大宽高，保持原比例，不裁剪

    :param img: PIL Image对象
    :param max_w: 最大宽度
    :param max_h: 最大高度
    :returns: 调整后的PIL Image对象
    :raises KeyError: 无
    """
    ow, oh = img.size

    # 计算限制比例
    ratio_w = max_w / ow
    ratio_h = max_h / oh
    ratio = min(ratio_w, ratio_h, 1.0)  # 不放大，只缩小

    if ratio >= 1.0:
        return img  # 尺寸本来就合规

    new_w = int(ow * ratio)
    new_h = int(oh * ratio)
    return img.resize((new_w, new_h), Image.LANCZOS)
