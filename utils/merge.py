from PIL import Image
import math


def merge_images_grid(image_paths, target_width=1500, padding=6, bg_color=(255, 255, 255)):
    """
    高性能拼贴图版本
    - 所有缩放使用 thumbnail(BILINEAR)
    - 不创建不必要的中间大图
    - 保留原有布局算法
    """

    images = []
    for p in image_paths:
        img = Image.open(p).convert("RGB")
        # 先限制单张最大宽度，加速后续 resize
        img.thumbnail((target_width, target_width), Image.BILINEAR)
        images.append(img)

    n = len(images)
    if n == 0:
        raise ValueError("No images provided")

    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    groups = []
    idx = 0
    for _ in range(rows):
        rem = n - idx
        count = min(cols, rem)
        groups.append(images[idx:idx + count])
        idx += count

    total_h = 0
    row_scaled = []

    for row_imgs in groups:
        ratios = [img.width / img.height for img in row_imgs]
        total_ratio = sum(ratios)
        row_h = int(target_width / total_ratio)

        scaled_row = []
        for img, r in zip(row_imgs, ratios):
            new_w = int(row_h * r)

            # 这里使用 resize(BILINEAR)，比 LANCZOS 快很多
            scaled_row.append(img.resize((new_w, row_h), Image.BILINEAR))

        row_scaled.append(scaled_row)
        total_h += row_h + padding

    canvas = Image.new("RGB", (target_width, total_h - padding), bg_color)

    y = 0
    for row in row_scaled:
        x = 0
        for img in row:
            canvas.paste(img, (x, y))
            x += img.width + padding
            img.close()
        y += row[0].height + padding

    return canvas


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
