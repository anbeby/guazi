# -*- coding: utf-8 -*-
{
    'name': '瓜子油料平台交易 (GZ Trade)',
    'version': '17.0.1.0.0',
    'summary': '询价/报价/平台订单/合同/结算/交易流水，以及与 sale/purchase/account 的对接',
    'description': """
第十师瓜子油料数字化交易平台 —— 交易域模块
==========================================

自研平台是 B2B 撮合交易的主承载方（docs/02 第 1.1 节），Odoo 侧承载：

* ``gz.inquiry`` / ``gz.quotation``：询价与报价的**镜像单据**，供 Odoo 内部
  运营、财务查看与审核；
* ``gz.order`` / ``gz.order.line``：平台订单及明细；
  - 确认订单：写 ``stock_deducted``、生成订单轨迹 ``gz.order.timeline``；
  - **生成 Odoo 销售单**：``sale.order``（``client_order_ref`` = 平台订单号）；
  - **生成 Odoo 采购单**：``purchase.order``（``partner_ref`` = 平台订单号）；
  - **生成结算凭证草稿**：``account.move``（``ref`` = 平台订单号 / 结算单号）；
* ``gz.contract``：平台合同（买方 / 卖方双边签署后生效）；
* ``gz.settlement`` / ``gz.settlement.line``：平台结算单（应收 / 应付 / 园区费用），
  确认时生成 ``account.move`` 草稿（``ref`` = 结算单号）；
* ``gz.trade.flow``：平台交易流水（资金方向、支付方式、支付状态）；
* ``data/gz_trade_cron.xml``：每 30 分钟执行 ``gz.order._cron_sync_platform()``，
  预留与自研平台 ``/api/v1/integration/odoo/*`` 的 REST 对接调用点（try/except 容错）。

幂等键（docs/02 第 2.1 节）：``order.name`` ↔ ``sale.order.client_order_ref`` /
``purchase.order.partner_ref``；``settlement.name`` ↔ ``account.move.ref``。
""",
    'author': '第十师瓜子油料数字化交易平台项目组',
    'website': 'https://gz.example.com',
    'license': 'LGPL-3',
    'category': '瓜子油料平台',
    'depends': ['gz_product', 'gz_inventory', 'sale_management', 'purchase', 'account'],
    'data': [
        'data/gz_sequence.xml',
        'data/gz_trade_cron.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/gz_inquiry_views.xml',
        'views/gz_quotation_views.xml',
        'views/gz_order_views.xml',
        'views/gz_contract_views.xml',
        'views/gz_settlement_views.xml',
        'views/gz_trade_flow_views.xml',
        'views/gz_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
