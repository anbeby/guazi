# -*- coding: utf-8 -*-
"""商户域：通过 _inherit 扩展企业主体（docs/03 第 2 节“主体域”）。

本模块只使用官方扩展点 ``_inherit``，不修改 gz_platform_base 的原始定义，
保证模块可独立升级 / 卸载。
"""

from odoo import api, fields, models

MERCHANT_LEVELS = [
    ('A', 'A 级'),
    ('B', 'B 级'),
    ('C', 'C 级'),
]


class GzEnterprise(models.Model):
    _inherit = 'gz.enterprise'

    # ------------------------------------------------------------------ 证照
    license_no = fields.Char(
        string='营业执照号', tracking=True,
        help='营业执照注册号；统一社会信用代码见 unified_social_credit_code。')
    food_production_license = fields.Char(
        string='食品生产许可证号', tracking=True, help='SC 编号，如 SC10265900100001。')

    # ------------------------------------------------------------------ 商户能力
    merchant_level = fields.Selection(
        MERCHANT_LEVELS, string='商户等级', index=True, tracking=True,
        help='平台按经营规模、资质、履约情况评定的等级。')
    annual_capacity = fields.Float(
        string='年产能（吨）', digits=(16, 3), tracking=True,
        help='加工 / 贸易年产能，单位：吨。')
    main_products = fields.Char(
        string='主营产品', tracking=True,
        help='如：葵花籽、南瓜籽、打瓜籽、炒货成品。')

    # ------------------------------------------------------------------ 关联
    qualification_ids = fields.One2many(
        'gz.merchant.qualification', 'enterprise_id', string='资质附件')
    qualification_count = fields.Integer(
        string='资质数量', compute='_compute_qualification_stats')
    expired_qualification_count = fields.Integer(
        string='过期资质数量', compute='_compute_qualification_stats')
    entry_ids = fields.One2many(
        'gz.merchant.entry', 'enterprise_id', string='入驻申请')

    @api.depends('qualification_ids', 'qualification_ids.state')
    def _compute_qualification_stats(self):
        for rec in self:
            rec.qualification_count = len(rec.qualification_ids)
            rec.expired_qualification_count = len(
                rec.qualification_ids.filtered(lambda q: q.state == 'expired'))
