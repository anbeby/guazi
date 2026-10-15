# -*- coding: utf-8 -*-
{
    'name': '瓜子油料平台库存 (GZ Inventory)',
    'version': '17.0.1.0.0',
    'summary': '库存批次、质检状态、仓储参数与库存预警',
    'description': """
第十师瓜子油料数字化交易平台 —— 库存域模块
==========================================

Odoo 侧库存账实以原生 ``stock`` 为准（docs/02 第 1.1 节），本模块只做
“平台视角”的批次与仓储参数承载：

* ``gz.stock.batch``：平台批次（批次号 ``GZ-BATCH-<年>-<流水>``、商品、企业、
  仓库、生产/失效日期、数量、质检状态、检测报告、溯源码、种植基地），
  并据此计算库存预警（``below_warn_qty``：数量 < 商品 ``gz_stock_warn_qty``）；
* ``gz.warehouse.config``：仓储参数（库位数、库容、是否温控）；
* ``_inherit stock.lot``：原生批次/序列号挂接平台批次、质检状态与溯源码；
* 视图：批次 列表 / 表单 / 搜索、库存预警、仓储参数；
  菜单：仓储管理 → 批次管理 / 库存预警 / 仓储参数。
""",
    'author': '第十师瓜子油料数字化交易平台项目组',
    'website': 'https://gz.example.com',
    'license': 'LGPL-3',
    'category': '瓜子油料平台',
    'depends': ['gz_product', 'stock'],
    'data': [
        'data/gz_sequence.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/gz_stock_batch_views.xml',
        'views/gz_warehouse_config_views.xml',
        'views/stock_lot_views.xml',
        'views/gz_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
