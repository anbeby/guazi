# -*- coding: utf-8 -*-
"""演示阶段的分类图片兜底；企业上传的商品主图优先。"""


def public_product_image(main_image: str | None, category_code: str) -> str:
    if main_image:
        return main_image
    if "KERNEL" in category_code:
        return "/demo/kernel.png"
    if "PUM" in category_code:
        return "/demo/pumpkin.png"
    if "SEED" in category_code:
        return "/demo/melon.png"
    if "ROAST" in category_code:
        return "/demo/roasted.png"
    return "/demo/sunflower.png"
