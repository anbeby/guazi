# -*- coding: utf-8 -*-
"""平台商品审核日志 gz.product.audit.log。

记录商品在平台侧的提交、审核、上架、下架动作，作为 Odoo → 自研平台
同步（/products/{id}/audit）的本地留痕。
"""

from odoo import fields, models

AUDIT_ACTIONS = [
    ('submit', '提交审核'),
    ('approve', '审核通过'),
    ('reject', '审核驳回'),
    ('publish', '上架'),
    ('offline', '下架'),
]


class GzProductAuditLog(models.Model):
    _name = 'gz.product.audit.log'
    _description = '瓜子油料平台商品审核日志'
    _order = 'event_time desc, id desc'
    _rec_name = 'action'

    product_tmpl_id = fields.Many2one(
        'product.template', string='商品', required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string='产品变体', ondelete='set null')
    action = fields.Selection(AUDIT_ACTIONS, string='动作', required=True, index=True)
    note = fields.Text(string='说明')
    operator_id = fields.Many2one(
        'res.users', string='操作人', default=lambda self: self.env.user)
    event_time = fields.Datetime(
        string='发生时间', default=fields.Datetime.now, required=True, index=True)
