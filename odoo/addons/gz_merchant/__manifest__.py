# -*- coding: utf-8 -*-
{
    'name': '瓜子油料平台商户 (GZ Merchant)',
    'version': '17.0.1.0.0',
    'summary': '商户档案扩展、资质附件、入驻申请与审核流程',
    'description': """
第十师瓜子油料数字化交易平台 —— 商户域模块
==========================================

* 通过 ``_inherit`` 扩展 ``gz.enterprise``：营业执照号、食品生产许可证号、
  商户等级（A/B/C）、年产能、主营产品、资质附件；
* ``gz.merchant.qualification`` 资质附件（证照 / 检测报告，含有效期与到期状态）；
* ``gz.merchant.entry`` 入驻申请：申请 → 提交 → 审核通过 / 驳回，
  通过后回填企业主体的园区与档口信息（阶段一为 Char 占位字段）；
* 商户档案、入驻申请列表 / 表单 / 看板视图，菜单挂在 ``瓜子油料平台`` 根菜单下。
""",
    'author': '第十师瓜子油料数字化交易平台项目组',
    'website': 'https://gz.example.com',
    'license': 'LGPL-3',
    'category': '瓜子油料平台',
    'depends': ['gz_platform_base', 'mail'],
    'data': [
        'data/gz_sequence.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/gz_enterprise_views.xml',
        'views/gz_merchant_qualification_views.xml',
        'views/gz_merchant_entry_views.xml',
        'views/gz_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
