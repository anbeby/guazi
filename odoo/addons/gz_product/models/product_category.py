# -*- coding: utf-8 -*-
"""瓜子油料分类：扩展 product.category。

自研平台分类树（docs/03 第 3 节）：
    瓜子油料(GZ)
    ├── 葵花籽(GZ-SUN)   ├── 南瓜籽(GZ-PUM)
    ├── 打瓜籽(GZ-SEED)  └── 加工产品(GZ-PRO)
                              ├── 炒货成品 / 榨油原料 / 饲料原料

Odoo 侧沿用原生 ``product.category``，仅追加平台需要的分类属性，
预置数据见 ``data/gz_product_category.xml``。
"""

from odoo import fields, models

#: 瓜子油料一级分类类型，与自研平台 category 语义对齐
GZ_CATEGORY_TYPES = [
    ('sunflower', '葵花籽'),
    ('pumpkin', '南瓜籽'),
    ('seed', '打瓜籽'),
    ('processed', '加工产品'),
    ('other', '其他'),
]


class ProductCategory(models.Model):
    _inherit = 'product.category'

    gz_category_type = fields.Selection(
        GZ_CATEGORY_TYPES, string='瓜子油料分类类型', index=True)
    gz_code = fields.Char(
        string='平台分类编码', copy=False,
        help='与自研平台 category.code 对齐，如 GZ、GZ-SUN、GZ-PRO-ROAST。')
    gz_is_leaf = fields.Boolean(
        string='叶子分类', default=False,
        help='仅叶子分类允许挂商品，便于平台侧做分类标准化校验。')
