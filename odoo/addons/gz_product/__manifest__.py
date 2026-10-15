# -*- coding: utf-8 -*-
{
    'name': '瓜子油料平台商品 (GZ Product)',
    'version': '17.0.1.0.0',
    'summary': '瓜子油料分类树、商品扩展字段（规格/等级/产地/年份/包装/检测报告）与发布审核',
    'description': """
第十师瓜子油料数字化交易平台 —— 商品域模块
==========================================

* ``_inherit product.category``：追加 ``gz_category_type``（葵花籽 / 南瓜籽 /
  打瓜籽 / 加工产品 / 其他）、``gz_code``（平台统一分类编码）、``gz_is_leaf``；
* ``_inherit product.template``：追加商品归属商户、规格、等级、产地、年份、包装、
  质检状态、检测报告、溯源开关、平台发布状态与审核状态、起订量、库存预警值；
* 商品发布前置校验：未通过平台审核（``gz_audit_status != 'approved'``）不允许上架；
* ``gz.product.audit.log`` 平台商品审核日志（提交 / 通过 / 驳回 / 上架 / 下架）；
* 预置瓜子油料分类树（``noupdate="1"``），编码与自研平台 ``category.code`` 对齐。
""",
    'author': '第十师瓜子油料数字化交易平台项目组',
    'website': 'https://gz.example.com',
    'license': 'LGPL-3',
    'category': '瓜子油料平台',
    'depends': ['gz_platform_base', 'product', 'stock'],
    'data': [
        'data/gz_product_category.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/product_category_views.xml',
        'views/gz_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
