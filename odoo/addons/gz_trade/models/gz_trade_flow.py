# -*- coding: utf-8 -*-
"""平台交易流水 gz.trade.flow。

对应自研平台 ``transaction_flow``（docs/03 第 5 节）。平台**不自建支付通道**，
只做流水与对账（docs/02 ADR-07），因此本模型只登记资金流水事实。
"""

from odoo import fields, models, _

FLOW_DIRECTIONS = [
    ('in', '收入'),
    ('out', '支出'),
]

FLOW_BIZ_TYPES = [
    ('order_payment', '订单货款'),
    ('service_fee', '平台服务费'),
    ('refund', '退款'),
    ('deposit', '保证金'),
]

FLOW_PAY_METHODS = [
    ('bank_transfer', '银行转账'),
    ('offline', '线下'),
    ('other', '其他'),
]

FLOW_PAY_STATUS = [
    ('pending', '待支付'),
    ('success', '支付成功'),
    ('failed', '支付失败'),
]


class GzTradeFlow(models.Model):
    _name = 'gz.trade.flow'
    _description = '瓜子油料平台交易流水'
    _order = 'paid_at desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='流水号', required=True, copy=False, readonly=True, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('gz.trade.flow') or _('New'))
    order_id = fields.Many2one(
        'gz.order', string='关联平台订单', ondelete='set null', index=True)
    enterprise_id = fields.Many2one(
        'gz.enterprise', string='企业', required=True, index=True)
    direction = fields.Selection(
        FLOW_DIRECTIONS, string='资金方向', required=True, default='in', index=True)
    biz_type = fields.Selection(
        FLOW_BIZ_TYPES, string='业务类型', required=True,
        default='order_payment', index=True)
    amount = fields.Monetary(
        string='金额', currency_field='currency_id', required=True)
    currency_id = fields.Many2one(
        'res.currency', string='币种', required=True,
        default=lambda self: self.env.company.currency_id)
    pay_method = fields.Selection(
        FLOW_PAY_METHODS, string='支付方式', default='bank_transfer', required=True)
    pay_status = fields.Selection(
        FLOW_PAY_STATUS, string='支付状态', default='pending', required=True, index=True)
    trade_no = fields.Char(
        string='外部交易号', copy=False, help='银行流水号 / 第三方支付单号。')
    paid_at = fields.Datetime(string='支付时间')
    remark = fields.Char(string='备注')

    # ================================================================== 业务方法
    def action_mark_success(self):
        """登记支付成功。"""
        for rec in self:
            rec.write({
                'pay_status': 'success',
                'paid_at': rec.paid_at or fields.Datetime.now(),
            })
        return True

    def action_mark_failed(self):
        """登记支付失败。"""
        self.write({'pay_status': 'failed'})
        return True
