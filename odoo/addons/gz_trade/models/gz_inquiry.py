# -*- coding: utf-8 -*-
"""平台询价单 gz.inquiry。

自研平台是询价单的**源系统**（docs/04 第 2.7 节），本模型是 Odoo 侧镜像，
供园区运营、财务查看与内部协同；状态与自研平台保持一致：
``draft / submitted / quoted / confirmed / closed / cancelled``。
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

INQUIRY_STATES = [
    ('draft', '草稿'),
    ('submitted', '已提交'),
    ('quoted', '已报价'),
    ('confirmed', '已确认'),
    ('closed', '已关闭'),
    ('cancelled', '已取消'),
]


class GzInquiry(models.Model):
    _name = 'gz.inquiry'
    _description = '瓜子油料平台询价单'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='询价单号', required=True, copy=False, readonly=True, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('gz.inquiry') or _('New'))
    buyer_enterprise_id = fields.Many2one(
        'gz.enterprise', string='采购企业', required=True, index=True, tracking=True,
        default=lambda self: self.env['gz.enterprise']._gz_get_user_enterprise(),
        help='默认取当前用户往来单位关联的企业主体。')
    supplier_enterprise_id = fields.Many2one(
        'gz.enterprise', string='指定供应商', index=True, tracking=True,
        help='留空表示公开询价，由平台撮合多个供应商报价。')
    product_id = fields.Many2one(
        'product.product', string='询价商品', required=True, index=True)
    product_tmpl_id = fields.Many2one(
        'product.template', string='商品模板', related='product_id.product_tmpl_id',
        store=True, index=True)
    quantity = fields.Float(string='数量', digits=(16, 3), required=True, default=1.0)
    unit = fields.Char(string='计量单位', default='吨')
    expect_price = fields.Monetary(
        string='期望单价', currency_field='currency_id',
        help='期望含税单价，平台参考价。')
    currency_id = fields.Many2one(
        'res.currency', string='币种', required=True,
        default=lambda self: self.env.company.currency_id)
    expect_delivery_date = fields.Date(string='期望交货日期')
    delivery_address = fields.Char(string='交货地址')
    state = fields.Selection(
        INQUIRY_STATES, string='状态', default='draft', required=True,
        tracking=True, index=True, copy=False)
    quotation_ids = fields.One2many('gz.quotation', 'inquiry_id', string='报价单')
    quoted_count = fields.Integer(
        string='报价数', compute='_compute_quoted_count', store=True)
    remark = fields.Text(string='备注')

    # ================================================================== 计算
    @api.depends('quotation_ids', 'quotation_ids.state')
    def _compute_quoted_count(self):
        for rec in self:
            rec.quoted_count = len(rec.quotation_ids)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id and rec.product_id.uom_id:
                rec.unit = rec.product_id.uom_id.name

    # ================================================================== 业务方法
    def action_submit(self):
        """提交询价（进入待报价）。"""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('只有「草稿」状态的询价单可以提交，当前状态：%s')
                                % dict(INQUIRY_STATES).get(rec.state, rec.state))
            rec.write({'state': 'submitted'})
            rec.message_post(body=_('询价单已提交，等待供应商报价。'))
        return True

    def action_reset_draft(self):
        """撤回为草稿。"""
        for rec in self:
            if rec.state in ('confirmed', 'closed'):
                raise UserError(_('已确认或已关闭的询价单不能撤回为草稿。'))
            rec.write({'state': 'draft'})
        return True

    def action_cancel(self):
        """取消询价：已确认（已生成订单）的询价单不允许取消。"""
        for rec in self:
            if rec.state == 'confirmed':
                raise UserError(_('询价单「%s」已确认并生成订单，不能取消。') % rec.name)
            if rec.state == 'cancelled':
                continue
            rec.write({'state': 'cancelled'})
            rec.message_post(body=_('询价单已取消。'))
        return True

    def action_close(self):
        """关闭询价。"""
        for rec in self:
            if rec.state == 'cancelled':
                raise UserError(_('已取消的询价单不能关闭。'))
            rec.write({'state': 'closed'})
        return True

    def action_view_quotations(self):
        """查看该询价单下的报价单。"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('报价单'),
            'res_model': 'gz.quotation',
            'view_mode': 'tree,form',
            'domain': [('inquiry_id', '=', self.id)],
            'context': {'default_inquiry_id': self.id},
        }
