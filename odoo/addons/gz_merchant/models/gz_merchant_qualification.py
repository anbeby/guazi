# -*- coding: utf-8 -*-
"""商户资质附件 gz.merchant.qualification。

一个企业主体可挂多份证照 / 检测报告；``state`` 依据 ``expire_date``
自动推导（过期 / 30 天内到期 / 有效），人工作废（``invalid``）不会被覆盖。
"""

from odoo import api, fields, models

QUAL_TYPES = [
    ('license', '营业执照'),
    ('food_license', '食品生产许可证'),
    ('test_report', '检测报告'),
    ('other', '其他'),
]

QUAL_STATES = [
    ('valid', '有效'),
    ('expiring', '即将到期'),
    ('expired', '已过期'),
    ('invalid', '作废'),
]

#: 到期前多少天进入“即将到期”
EXPIRING_WARN_DAYS = 30


class GzMerchantQualification(models.Model):
    _name = 'gz.merchant.qualification'
    _description = '瓜子油料平台商户资质附件'
    _order = 'expire_date, id'
    _rec_name = 'name'

    enterprise_id = fields.Many2one(
        'gz.enterprise', string='所属企业', required=True,
        ondelete='cascade', index=True)
    name = fields.Char(string='资质名称', required=True,
                       help='如：营业执照（副本）、食品生产许可证、2025 年度检测报告。')
    qual_type = fields.Selection(
        QUAL_TYPES, string='资质类型', required=True, default='license', index=True)
    file = fields.Binary(string='附件', attachment=True)
    file_name = fields.Char(string='附件文件名')
    issue_date = fields.Date(string='发证日期')
    expire_date = fields.Date(string='有效期至')
    state = fields.Selection(
        QUAL_STATES, string='状态', default='valid', required=True,
        compute='_compute_state', store=True, readonly=False)
    days_to_expire = fields.Integer(
        string='剩余天数', compute='_compute_days_to_expire')
    remark = fields.Char(string='备注')

    _sql_constraints = [
        ('qual_name_type_uniq', 'unique(enterprise_id, name, qual_type)',
         '同一企业下资质名称与类型不能重复！'),
    ]

    # ================================================================== 计算
    @api.depends('expire_date')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state == 'invalid':
                # 人工作废的状态不因日期变化被覆盖
                continue
            if not rec.expire_date:
                rec.state = 'valid'
            elif rec.expire_date < today:
                rec.state = 'expired'
            elif (rec.expire_date - today).days <= EXPIRING_WARN_DAYS:
                rec.state = 'expiring'
            else:
                rec.state = 'valid'

    @api.depends('expire_date')
    def _compute_days_to_expire(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_to_expire = (rec.expire_date - today).days if rec.expire_date else 0

    # ================================================================== 业务方法
    def action_set_invalid(self):
        """作废资质附件。"""
        self.write({'state': 'invalid'})
        return True
