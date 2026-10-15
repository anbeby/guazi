# -*- coding: utf-8 -*-
"""平台结算单 gz.settlement / gz.settlement.line。

平台服务费率默认 0.5%（docs/03 第 5 节），按订单金额计提并写入
``fee_amount`` 与 ``settlement_line(biz_type=service_fee)``。

Odoo 侧落地：``action_confirm()`` 生成 ``account.move`` 草稿
（``ref`` = 结算单号，作为与自研平台 ``settlement.settlement_no`` 的幂等键）。
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: 平台默认服务费率（%），可由 ir.config_parameter 覆盖
DEFAULT_SERVICE_FEE_RATE = 0.5

SETTLE_TYPES = [
    ('receivable', '应收'),
    ('payable', '应付'),
    ('park_fee', '园区费用'),
]

PAY_STATUS = [
    ('unpaid', '未付款'),
    ('partial', '部分付款'),
    ('paid', '已付清'),
]

SETTLEMENT_STATES = [
    ('pending', '待确认'),
    ('confirmed', '已确认'),
    ('settled', '已结算'),
    ('cancelled', '已取消'),
]

SETTLEMENT_LINE_TYPES = [
    ('order', '订单货款'),
    ('park_fee', '园区费用'),
    ('service_fee', '平台服务费'),
]


class GzSettlement(models.Model):
    _name = 'gz.settlement'
    _description = '瓜子油料平台结算单'
    _inherit = ['gz.account.move.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'period_end desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='结算单号', required=True, copy=False, readonly=True, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('gz.settlement') or _('New'))
    enterprise_id = fields.Many2one(
        'gz.enterprise', string='结算企业', required=True, index=True, tracking=True)
    settle_type = fields.Selection(
        SETTLE_TYPES, string='结算类型', required=True, default='receivable',
        index=True, tracking=True)
    period_start = fields.Date(string='结算期间（起）', required=True,
                               default=lambda self: fields.Date.context_today(self).replace(day=1))
    period_end = fields.Date(string='结算期间（止）', required=True,
                             default=fields.Date.context_today)
    order_amount = fields.Monetary(
        string='订单金额', currency_field='currency_id', tracking=True)
    fee_amount = fields.Monetary(
        string='服务费 / 费用金额', currency_field='currency_id', tracking=True)
    settle_amount = fields.Monetary(
        string='应结算金额', currency_field='currency_id', tracking=True,
        compute='_compute_settle_amount', store=True, readonly=False,
        help='默认 = 订单金额 + 费用金额；如需扣减可手工覆盖（订单金额 / 费用金额变化时重算）。')
    settled_amount = fields.Monetary(
        string='已结算金额', currency_field='currency_id', readonly=True, copy=False)
    currency_id = fields.Many2one(
        'res.currency', string='币种', required=True,
        default=lambda self: self.env.company.currency_id)
    pay_status = fields.Selection(
        PAY_STATUS, string='付款状态', default='unpaid', required=True,
        tracking=True, index=True, copy=False)
    state = fields.Selection(
        SETTLEMENT_STATES, string='状态', default='pending', required=True,
        tracking=True, index=True, copy=False)
    line_ids = fields.One2many('gz.settlement.line', 'settlement_id', string='结算明细')
    move_id = fields.Many2one(
        'account.move', string='凭证草稿', readonly=True, copy=False, ondelete='set null')
    confirm_user_id = fields.Many2one('res.users', string='确认人', readonly=True, copy=False)
    confirm_date = fields.Datetime(string='确认时间', readonly=True, copy=False)
    settled_date = fields.Datetime(string='结算时间', readonly=True, copy=False)
    remark = fields.Text(string='备注')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', '结算单号必须唯一！'),
    ]

    # ================================================================== 联动与计算
    @api.depends('order_amount', 'fee_amount')
    def _compute_settle_amount(self):
        for rec in self:
            rec.settle_amount = (rec.order_amount or 0.0) + (rec.fee_amount or 0.0)

    @api.onchange('order_amount', 'settle_type')
    def _onchange_suggest_service_fee(self):
        """应收结算按平台费率（默认 0.5%）预填服务费。"""
        for rec in self:
            if rec.settle_type == 'receivable' and rec.order_amount and not rec.fee_amount:
                rec.fee_amount = rec.order_amount * rec._gz_service_fee_rate() / 100.0

    @api.onchange('enterprise_id', 'settle_type')
    def _onchange_enterprise(self):
        """按订单归集：默认汇总该企业在本期间内已完成的平台订单。"""
        for rec in self:
            if not rec.enterprise_id or rec.settle_type == 'park_fee':
                continue
            domain = [
                ('state', '=', 'completed'),
                '|', ('buyer_enterprise_id', '=', rec.enterprise_id.id),
                ('supplier_enterprise_id', '=', rec.enterprise_id.id),
            ]
            if rec.period_start:
                domain.append(('create_date', '>=', rec.period_start))
            if rec.period_end:
                domain.append(('create_date', '<=', rec.period_end))
            orders = self.env['gz.order'].search(domain)
            rec.order_amount = sum(orders.mapped('amount_total'))

    @api.model
    def _gz_service_fee_rate(self):
        """平台服务费率（%）：优先取系统参数，缺省 0.5%。"""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'gz_platform.service_fee_rate')
        try:
            return float(param) if param else DEFAULT_SERVICE_FEE_RATE
        except (TypeError, ValueError):
            _logger.warning('gz_platform.service_fee_rate 配置无效（%s），回退默认值。', param)
            return DEFAULT_SERVICE_FEE_RATE

    # ================================================================== 业务方法
    def action_confirm(self):
        """确认结算单并生成账务凭证草稿。"""
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('只有「待确认」的结算单可以确认，结算单「%s」当前状态：%s')
                                % (rec.name, dict(SETTLEMENT_STATES).get(rec.state, rec.state)))
            amount = rec.settle_amount or (rec.order_amount + rec.fee_amount)
            direction = 'payable' if rec.settle_type == 'payable' else 'receivable'
            move = rec._gz_create_draft_move(
                ref=rec.name,
                amount=amount,
                partner=rec.enterprise_id._gz_sync_partner(),
                label=_('平台结算单 %s（%s）') % (
                    rec.name, dict(SETTLE_TYPES).get(rec.settle_type, rec.settle_type)),
                direction=direction,
            )
            rec.write({
                'state': 'confirmed',
                'settle_amount': amount,
                'move_id': move.id,
                'confirm_user_id': self.env.user.id,
                'confirm_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('结算单已确认，生成凭证草稿 %s。') % move.name)
        return True

    def action_settle(self):
        """登记结算完成（全额）。"""
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_('只有「已确认」的结算单可以结算。'))
            rec.write({
                'state': 'settled',
                'pay_status': 'paid',
                'settled_amount': rec.settle_amount or (rec.order_amount + rec.fee_amount),
                'settled_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('结算单已完成结算。'))
        return True

    def action_cancel(self):
        """取消结算单（已确认的需先冲销凭证）。"""
        for rec in self:
            if rec.state == 'settled':
                raise UserError(_('已结算的结算单不能取消。'))
            if rec.state == 'confirmed' and rec.move_id and rec.move_id.state == 'posted':
                raise UserError(_('结算单已生成并过账凭证，请先在会计中冲销后再取消。'))
            rec.write({'state': 'cancelled'})
        return True

    def action_view_move(self):
        """查看生成的凭证草稿。"""
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('该结算单还没有生成凭证草稿。'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('凭证草稿'),
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class GzSettlementLine(models.Model):
    _name = 'gz.settlement.line'
    _description = '瓜子油料平台结算明细'
    _order = 'settlement_id, id'

    settlement_id = fields.Many2one(
        'gz.settlement', string='结算单', required=True,
        ondelete='cascade', index=True)
    biz_type = fields.Selection(
        SETTLEMENT_LINE_TYPES, string='业务类型', required=True, default='order')
    biz_no = fields.Char(
        string='业务单号', help='订单号 / 园区费用单号，与自研平台 biz_no 对齐。')
    amount = fields.Monetary(
        string='金额', currency_field='currency_id')
    fee_rate = fields.Float(
        string='费率（%）', digits=(5, 2), default=0.0,
        help='平台服务费或园区费用费率。')
    currency_id = fields.Many2one(
        'res.currency', string='币种', related='settlement_id.currency_id', store=True)
    remark = fields.Char(string='备注')
