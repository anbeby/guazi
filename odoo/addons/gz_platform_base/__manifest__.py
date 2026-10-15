# -*- coding: utf-8 -*-
{
    'name': '瓜子油料平台基础 (GZ Platform Base)',
    'version': '17.0.1.0.0',
    'summary': '企业主体档案、平台角色安全组、企业级数据隔离规则与企业编码序列',
    'description': """
第十师瓜子油料数字化交易平台 —— 企业侧 Odoo 基础模块
=====================================================

承载平台在 Odoo 侧的“主体域”基础能力（见 docs/02 第三节、docs/03 第 2 节）：

* ``gz.enterprise`` 企业主体档案（商户 / 供应商 / 采购商 / 平台），
  与自研平台 ``gz.enterprise`` 通过 ``code``、``unified_social_credit_code`` 一一对应；
* 与 ``res.partner`` 的同步关系：``ref`` = 企业编码、``vat`` = 统一社会信用代码、
  ``company_type`` = company，作为全 Odoo 的往来单位主键；
* 平台六类角色安全组：平台管理员 / 园区运营人员 / 商户 / 供应商 / 采购商 / 财务；
* 企业级数据隔离记录规则（商户 / 供应商 / 采购商仅可见本企业）；
* 企业编码序列 ``ENT-<年>-<流水>``（ir.sequence code = ``gz.enterprise``）。

阶段二 ``gz_park`` 模块将通过 ``_inherit`` 追加 ``park_id``，届时把本模块的
``park_name``（Char 占位）迁移为 Many2one，避免阶段一产生循环依赖。
""",
    'author': '第十师瓜子油料数字化交易平台项目组',
    'website': 'https://gz.example.com',
    'license': 'LGPL-3',
    'category': '瓜子油料平台',
    'depends': ['base', 'contacts', 'mail'],
    'data': [
        # 序列先于安全与视图加载
        'data/gz_sequence.xml',
        # 安全组与记录规则必须先于引用它们的视图
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/gz_enterprise_views.xml',
        'views/gz_menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
