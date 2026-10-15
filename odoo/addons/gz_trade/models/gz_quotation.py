# -*- coding: utf-8 -*-
"""平台报价单 gz.quotation。

供应商针对询价单报价；采购商接受报价后生成平台订单 ``gz.order``
（状态 ``pending_confirm``），同时把该询价单下其它报价置为已拒绝。
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

QUOTATION_STATES = [
    ('submitted', '已提交'),
    ('accepted', '已接受'),
    ('rejected', '已拒绝'),
    ('expired', '已失效'),
]


class GzQuotation(models.Model):
    _name = 'gz.quotation'
    _description = '瓜子油料平台报价单'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='报价单号', required=True, copy=False, readonly=True, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('gz.quotation') or _('New'))
    inquiry_id = fields.Many2one(
        'gz.inquiry', string='询价单', required=True,
        ondelete='cascade', index=True, tracking=True)
    buyer_enterprise_id = fields.Many2one(
        'gz.enterprise', string='采购企业', related='inquiry_id.buyer_enterprise_id',
        store=True, index=True)
    supplier_enterprise_id = fields.Many2one(
        'gz.enterprise', string='报价供应商', required=True, index=True, tracking=True,
        default=lambda self: self.env['gz.enterprise']._gz_get_user_enterprise())
    product_id = fields.Many2one(
        'product.product', string='商品', required=True, index=True)
    quantity = fields.Float(string='报价数量', digits=(16, 3), required=True, default=1.0)
    uom_id = fields.Many2one(
        'uom.uom', string='计量单位', related='product_id.uom_id', store=False)
    unit_price = fields.Monetary(
        string='报价单价', currency_field='currency_id', required=True)
    amount = fields.Monetary(
        string='报价金额', currency_field='currency_id',
        compute='_compute_amount', store=True)
    tax_rate = fields.Float(
        string='税率（%）', digits=(5, 2), default=0.0,
        help='平台侧计税用税率，百分数；Odoo 销售/采购单不重复计税。')
    currency_id = fields.Many2one(
        'res.currency', string='币种', required=True,
        default=lambda self: self.env.company.currency_id)
    valid_until = fields.Date(string='报价有效期至')
    delivery_date = fields.Date(string='承诺交货日期')
    payment_terms = fields.Char(string='付款条件', help='如：预付 30%，发货前付清')
    state = fields.Selection(
        QUOTATION_STATES, string='状态', default='submitted', required=True,
        tracking=True, index=True, copy=False)
    order_id = fields.Many2one(
        'gz.order', string='生成订单', readonly=True, copy=False, ondelete='set null')
    remark = fields.Text(string='备注')

    # ================================================================== 计算
    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for rec in self:
            rec.amount = (rec.quantity or 0.0) * (rec.unit_price or 0.0)

    # ================================================================== ORM
    @api.model_create_multi
    def create(self, vals_list):
        quotations = super().create(vals_list)
        # 首次报价后把询价单推进到「已报价」
        for quotation in quotations:
            inquiry = quotation.inquiry_id
            if inquiry and inquiry.state == 'submitted':
                inquiry.state = 'quoted'
        return quotations

    # ================================================================== 业务方法
    def action_accept(self):
        """接受报价：生成平台订单（待供方确认）。"""
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_('只有「已提交」的报价单可以接受，当前状态：%s')
                            % dict(QUOTATION_STATES).get(self.state, self.state))
        inquiry = self.inquiry_id
        order = self.env['gz.order'].create({
            'order_type': 'sales',
            'inquiry_id': inquiry.id,
            'quotation_id': self.id,
            'buyer_enterprise_id': inquiry.buyer_enterprise_id.id,
            'supplier_enterprise_id': self.supplier_enterprise_id.id,
            'currency_id': self.currency_id.id,
            'delivery_date': self.delivery_date or inquiry.expect_delivery_date,
            'delivery_address': inquiry.delivery_address,
            'state': 'pending_confirm',
            'remark': self.remark,
            'line_ids': [fields.Command.create({
                'product_id': self.product_id.id,
                'quantity': self.quantity,
                'unit_price': self.unit_price,
                'tax_rate': self.tax_rate,
            })],
        })
        self.write({'state': 'accepted', 'order_id': order.id})
        # 同一询价单的其它待处理报价自动拒绝
        (inquiry.quotation_ids - self).filtered(
            lambda q: q.state == 'submitted').write({'state': 'rejected'})
        inquiry.write({
            'state': 'confirmed',
            'supplier_enterprise_id': self.supplier_enterprise_id.id,
        })
        order._add_timeline('pending_confirm', _('由报价单 %s 生成平台订单。') % self.name)
        self.message_post(body=_('报价已被接受，生成平台订单 %s。') % order.name)
        return {
            'type': 'ir.actions.act_window',
            'name': _('平台订单'),
            'res_model': 'gz.order',
            'res_id': order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_reject(self):
        """拒绝报价。"""
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('只有「已提交」的报价单可以拒绝，当前状态：%s')
                                % dict(QUOTATION_STATES).get(rec.state, rec.state))
            rec.write({'state': 'rejected'})
            rec.message_post(body=_('报价已拒绝。'))
            inquiry = rec.inquiry_id
            if inquiry and inquiry.state == 'quoted' and not inquiry.quotation_ids.filtered(
                    lambda q: q.state == 'submitted'):
                inquiry.state = 'submitted'
        return True

    def action_expire(self):
        """把超过有效期且未处理的报价置为失效。"""
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state == 'submitted' and rec.valid_until and rec.valid_until < today:
                rec.state = 'expired'
        return True
