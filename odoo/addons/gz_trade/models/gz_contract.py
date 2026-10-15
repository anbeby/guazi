# -*- coding: utf-8 -*-
"""平台合同 gz.contract。

平台合同含三方（买方 / 卖方 / 平台）要素与在线签署，源系统为自研平台
（docs/02 第 1.1 节）；Odoo 侧承载合同要素、附件与签署状态：

``draft → pending_sign → signed → effective →（terminated / expired）``

双边签署（``action_sign_buyer`` / ``action_sign_supplier``）完成后自动进入
``signed``，再由运营/财务执行 ``action_effect`` 生效。
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

CONTRACT_STATES = [
    ('draft', '草稿'),
    ('pending_sign', '待签署'),
    ('signed', '已签署'),
    ('effective', '已生效'),
    ('terminated', '已终止'),
    ('expired', '已到期'),
]


class GzContract(models.Model):
    _name = 'gz.contract'
    _description = '瓜子油料平台合同'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sign_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='合同编号', required=True, copy=False, readonly=True, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('gz.contract') or _('New'))
    title = fields.Char(string='合同名称', required=True, tracking=True)
    order_id = fields.Many2one(
        'gz.order', string='关联平台订单', ondelete='set null', index=True)
    buyer_enterprise_id = fields.Many2one(
        'gz.enterprise', string='买方', required=True, index=True, tracking=True)
    supplier_enterprise_id = fields.Many2one(
        'gz.enterprise', string='卖方', required=True, index=True, tracking=True)
    amount = fields.Monetary(
        string='合同金额', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='币种', required=True,
        default=lambda self: self.env.company.currency_id)
    sign_date = fields.Date(string='签订日期', tracking=True)
    start_date = fields.Date(string='生效日期')
    end_date = fields.Date(string='到期日期')
    file = fields.Binary(string='合同附件', attachment=True)
    file_name = fields.Char(string='附件文件名')
    state = fields.Selection(
        CONTRACT_STATES, string='状态', default='draft', required=True,
        tracking=True, index=True, copy=False)
    signed_by_buyer = fields.Boolean(string='买方已签署', default=False, copy=False, tracking=True)
    signed_by_supplier = fields.Boolean(string='卖方已签署', default=False, copy=False, tracking=True)
    buyer_signed_at = fields.Datetime(string='买方签署时间', readonly=True, copy=False)
    supplier_signed_at = fields.Datetime(string='卖方签署时间', readonly=True, copy=False)
    terminated_reason = fields.Char(string='终止原因', copy=False)
    remark = fields.Text(string='备注')

    # ================================================================== 约束与联动
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_('合同到期日期不能早于生效日期。'))

    @api.onchange('order_id')
    def _onchange_order_id(self):
        for rec in self:
            if rec.order_id:
                rec.buyer_enterprise_id = rec.order_id.buyer_enterprise_id
                rec.supplier_enterprise_id = rec.order_id.supplier_enterprise_id
                if not rec.amount:
                    rec.amount = rec.order_id.amount_total
                if not rec.title:
                    rec.title = _('瓜子油料交易合同（%s）') % rec.order_id.name

    # ================================================================== 业务方法
    def action_submit(self):
        """提交待签署。"""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('只有「草稿」状态的合同可以提交待签署。'))
            rec.write({'state': 'pending_sign'})
        return True

    def action_sign_buyer(self):
        """买方签署。"""
        for rec in self:
            if rec.state not in ('draft', 'pending_sign'):
                raise UserError(_('合同「%s」当前状态为「%s」，不能签署。')
                                % (rec.name, dict(CONTRACT_STATES).get(rec.state, rec.state)))
            rec.write({
                'state': 'pending_sign',
                'signed_by_buyer': True,
                'buyer_signed_at': fields.Datetime.now(),
                'sign_date': fields.Date.context_today(rec),
            })
            rec._check_signed()
        return True

    def action_sign_supplier(self):
        """卖方签署。"""
        for rec in self:
            if rec.state not in ('draft', 'pending_sign'):
                raise UserError(_('合同「%s」当前状态为「%s」，不能签署。')
                                % (rec.name, dict(CONTRACT_STATES).get(rec.state, rec.state)))
            rec.write({
                'state': 'pending_sign',
                'signed_by_supplier': True,
                'supplier_signed_at': fields.Datetime.now(),
                'sign_date': fields.Date.context_today(rec),
            })
            rec._check_signed()
        return True

    def action_effect(self):
        """合同生效（需双边已签署）。"""
        for rec in self:
            if not (rec.signed_by_buyer and rec.signed_by_supplier):
                raise UserError(_('合同「%s」尚未完成买卖双方签署，不能生效。') % rec.name)
            rec.write({'state': 'effective'})
            rec.message_post(body=_('合同已生效。'))
        return True

    def action_terminate(self):
        """终止合同。"""
        for rec in self:
            if rec.state in ('terminated', 'expired'):
                continue
            rec.write({'state': 'terminated'})
            rec.message_post(body=_('合同已终止：%s') % (rec.terminated_reason or _('未填写原因')))
        return True

    def action_reset_draft(self):
        """撤回为草稿（清空签署标记）。"""
        for rec in self:
            if rec.state == 'effective':
                raise UserError(_('已生效的合同不能撤回为草稿。'))
            rec.write({
                'state': 'draft',
                'signed_by_buyer': False,
                'signed_by_supplier': False,
                'buyer_signed_at': False,
                'supplier_signed_at': False,
            })
        return True

    def _check_signed(self):
        """双边签署完成后进入「已签署」。"""
        self.ensure_one()
        if self.signed_by_buyer and self.signed_by_supplier:
            self.state = 'signed'
            self.message_post(body=_('买卖双方已完成签署。'))
        return True
