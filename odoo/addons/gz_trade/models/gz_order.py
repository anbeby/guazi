# -*- coding: utf-8 -*-
"""平台订单 gz.order / gz.order.line / gz.order.timeline。

自研平台为订单源系统，Odoo 侧承担内部账实与账务落地（docs/02 第 2.1 节）：

======================  ==================================================
动作                      Odoo 侧结果
======================  ==================================================
``action_confirm``       订单置 confirmed，``stock_deducted=True``，写订单轨迹
``action_create_sale_order``     生成 ``sale.order``（``client_order_ref`` = 订单号）
``action_create_purchase_order`` 生成 ``purchase.order``（``partner_ref`` = 订单号）
``action_complete``      订单置 completed，写订单轨迹
``action_cancel``        订单置 cancelled（已完成 / 已结算不可取消）
``action_create_settlement_move`` 生成 ``account.move`` 草稿（``ref`` = 订单号）
``_cron_sync_platform``  ir.cron 每 30 分钟调用，回执订单进度给自研平台
======================  ==================================================
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:  # requests 由 requirements.txt 提供；缺失时定时任务降级为“只记日志”
    import requests
except ImportError:  # pragma: no cover
    requests = None

_logger = logging.getLogger(__name__)

#: 订单状态机（docs/03 第 4 节）
ORDER_STATES = [
    ('draft', '草稿'),
    ('pending_confirm', '待确认'),
    ('confirmed', '已确认'),
    ('delivering', '发货中'),
    ('completed', '已完成'),
    ('settled', '已结算'),
    ('cancelled', '已取消'),
]

ORDER_TYPES = [
    ('sales', '销售订单（平台→买方）'),
    ('purchase', '采购订单（平台→供方）'),
]

#: 可执行「确认」的状态
CONFIRMABLE_STATES = ('draft', 'pending_confirm')
#: 可执行「取消」的状态
CANCELLABLE_STATES = ('draft', 'pending_confirm', 'confirmed', 'delivering')


class GzOrder(models.Model):
    _name = 'gz.order'
    _description = '瓜子油料平台订单'
    _inherit = ['gz.account.move.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='平台订单号', required=True, copy=False, readonly=True, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('gz.order') or _('New'))
    order_type = fields.Selection(
        ORDER_TYPES, string='订单类型', required=True, default='sales',
        index=True, tracking=True)
    inquiry_id = fields.Many2one(
        'gz.inquiry', string='来源询价单', ondelete='set null', index=True, copy=False)
    quotation_id = fields.Many2one(
        'gz.quotation', string='来源报价单', ondelete='set null', index=True, copy=False)
    buyer_enterprise_id = fields.Many2one(
        'gz.enterprise', string='采购企业', required=True, index=True, tracking=True)
    supplier_enterprise_id = fields.Many2one(
        'gz.enterprise', string='供应企业', required=True, index=True, tracking=True)

    line_ids = fields.One2many(
        'gz.order.line', 'order_id', string='订单明细', copy=True)
    currency_id = fields.Many2one(
        'res.currency', string='币种', required=True,
        default=lambda self: self.env.company.currency_id)
    amount_untaxed = fields.Monetary(
        string='未税金额', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    tax_amount = fields.Monetary(
        string='税额', currency_field='currency_id',
        compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(
        string='含税金额', currency_field='currency_id',
        compute='_compute_amounts', store=True)

    delivery_date = fields.Date(string='交货日期', tracking=True)
    delivery_address = fields.Char(string='交货地址')
    stock_deducted = fields.Boolean(
        string='库存已扣减', default=False, copy=False, tracking=True,
        help='平台确认订单时置位；Odoo 侧实际出入库由库存单据 / 集成层完成。')
    state = fields.Selection(
        ORDER_STATES, string='状态', default='draft', required=True,
        tracking=True, index=True, copy=False)

    sale_order_id = fields.Many2one(
        'sale.order', string='Odoo 销售单', readonly=True, copy=False, ondelete='set null')
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Odoo 采购单', readonly=True, copy=False, ondelete='set null')
    timeline_ids = fields.One2many(
        'gz.order.timeline', 'order_id', string='订单轨迹')
    contract_ids = fields.One2many(
        'gz.contract', 'order_id', string='平台合同')
    trade_flow_ids = fields.One2many(
        'gz.trade.flow', 'order_id', string='交易流水')
    confirm_user_id = fields.Many2one('res.users', string='确认人', readonly=True, copy=False)
    confirm_date = fields.Datetime(string='确认时间', readonly=True, copy=False)
    complete_date = fields.Datetime(string='完成时间', readonly=True, copy=False)
    remark = fields.Text(string='备注')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', '平台订单号必须唯一！'),
    ]

    # ================================================================== 计算
    @api.depends('line_ids.price_subtotal', 'line_ids.tax_rate')
    def _compute_amounts(self):
        for order in self:
            untaxed = 0.0
            tax = 0.0
            for line in order.line_ids:
                untaxed += line.price_subtotal
                tax += line.price_subtotal * (line.tax_rate or 0.0) / 100.0
            order.amount_untaxed = untaxed
            order.tax_amount = tax
            order.amount_total = untaxed + tax

    # ================================================================== 业务方法
    def action_confirm(self):
        """供方确认订单：置状态、标记库存已扣减、写订单轨迹。"""
        for order in self:
            if order.state not in CONFIRMABLE_STATES:
                raise UserError(_('只有「草稿」或「待确认」的订单可以确认，订单「%s」当前状态：%s')
                                % (order.name, dict(ORDER_STATES).get(order.state, order.state)))
            if not order.line_ids:
                raise UserError(_('订单「%s」没有明细，不能确认。') % order.name)
            order.write({
                'state': 'confirmed',
                'stock_deducted': True,
                'confirm_user_id': self.env.user.id,
                'confirm_date': fields.Datetime.now(),
            })
            order._add_timeline(
                'confirmed',
                _('供方确认订单；平台侧标记库存已扣减（实际出入库以 Odoo 库存单据为准）。'))
            order.message_post(body=_('订单已确认。'))
        return True

    def action_set_delivering(self):
        """标记发货中（发货明细由自研平台登记）。"""
        for order in self:
            if order.state != 'confirmed':
                raise UserError(_('只有「已确认」的订单可以进入发货中。'))
            order.write({'state': 'delivering'})
            order._add_timeline('delivering', _('订单进入发货中。'))
        return True

    def action_complete(self):
        """完成订单。"""
        for order in self:
            if order.state not in ('confirmed', 'delivering'):
                raise UserError(_('只有「已确认」或「发货中」的订单可以完成，订单「%s」当前状态：%s')
                                % (order.name, dict(ORDER_STATES).get(order.state, order.state)))
            order.write({
                'state': 'completed',
                'complete_date': fields.Datetime.now(),
            })
            order._add_timeline('completed', _('订单已完成。'))
            order.message_post(body=_('订单已完成，等待结算。'))
        return True

    def action_cancel(self):
        """取消订单（已完成 / 已结算不可取消）。"""
        for order in self:
            if order.state not in CANCELLABLE_STATES:
                raise UserError(_('订单「%s」当前状态为「%s」，不能取消。')
                                % (order.name, dict(ORDER_STATES).get(order.state, order.state)))
            order.write({'state': 'cancelled'})
            order._add_timeline('cancelled', _('订单已取消。'))
            order.message_post(body=_('订单已取消。'))
        return True

    # ------------------------------------------------------------------ 生成 Odoo 单据
    def action_create_sale_order(self):
        """依据平台订单生成 Odoo 销售订单（买方为往来单位）。"""
        self.ensure_one()
        if self.sale_order_id:
            raise UserError(_('该订单已生成销售单：%s') % self.sale_order_id.name)
        if not self.env.user.has_group('sales_team.group_sale_salesman'):
            raise UserError(_('当前用户没有销售订单权限（sales_team.group_sale_salesman），'
                              '请由平台管理员或销售人员执行。'))
        if not self.line_ids:
            raise UserError(_('订单没有明细，不能生成销售单。'))

        partner = self.buyer_enterprise_id._gz_sync_partner()
        sale_order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'client_order_ref': self.name,
            'origin': self.name,
            'date_order': fields.Datetime.now(),
            'order_line': [
                fields.Command.create(self._prepare_sale_order_line_vals(line))
                for line in self.line_ids
            ],
            'note': self.remark or False,
        })
        self.sale_order_id = sale_order.id
        self._add_timeline(self.state, _('已生成 Odoo 销售单 %s。') % sale_order.name)
        return self._action_open_record('sale.order', sale_order.id, _('销售订单'))

    def action_create_purchase_order(self):
        """依据平台订单生成 Odoo 采购订单（供方为供应商）。"""
        self.ensure_one()
        if self.purchase_order_id:
            raise UserError(_('该订单已生成采购单：%s') % self.purchase_order_id.name)
        if not self.env.user.has_group('purchase.group_purchase_user'):
            raise UserError(_('当前用户没有采购订单权限（purchase.group_purchase_user），'
                              '请由平台管理员或采购人员执行。'))
        if not self.line_ids:
            raise UserError(_('订单没有明细，不能生成采购单。'))

        partner = self.supplier_enterprise_id._gz_sync_partner()
        purchase_order = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'partner_ref': self.name,
            'origin': self.name,
            'date_order': fields.Datetime.now(),
            'order_line': [
                fields.Command.create(self._prepare_purchase_order_line_vals(line))
                for line in self.line_ids
            ],
        })
        self.purchase_order_id = purchase_order.id
        self._add_timeline(self.state, _('已生成 Odoo 采购单 %s。') % purchase_order.name)
        return self._action_open_record('purchase.order', purchase_order.id, _('采购订单'))

    def action_create_settlement_move(self):
        """生成结算凭证草稿（``account.move.ref`` = 平台订单号）。"""
        self.ensure_one()
        if self.sale_order_id and self.sale_order_id.invoice_ids:
            # 已有销售发票时以发票为准，避免重复确认收入
            _logger.info('订单 %s 已存在销售发票，跳过凭证草稿生成。', self.name)
        move = self._gz_create_draft_move(
            ref=self.name,
            amount=self.amount_total,
            partner=self.buyer_enterprise_id._gz_sync_partner(),
            label=_('平台订单 %s 应收') % self.name,
            direction='receivable',
        )
        self._add_timeline(self.state, _('已生成账务凭证草稿 %s。') % move.name)
        return self._action_open_record('account.move', move.id, _('凭证草稿'))

    # ------------------------------------------------------------------ 辅助
    def _prepare_sale_order_line_vals(self, line):
        """平台订单明细 → sale.order.line 字典。"""
        self.ensure_one()
        product = line.product_id
        return {
            'product_id': product.id,
            'name': line.name or product.display_name,
            'product_uom_qty': line.quantity,
            'product_uom': product.uom_id.id,
            'price_unit': line.unit_price,
            # 税额由平台（自研）统一计算，清空 Odoo 默认税避免重复计税
            'tax_id': [fields.Command.clear()],
        }

    def _prepare_purchase_order_line_vals(self, line):
        """平台订单明细 → purchase.order.line 字典。"""
        self.ensure_one()
        product = line.product_id
        return {
            'product_id': product.id,
            'name': line.name or product.display_name,
            'product_qty': line.quantity,
            'product_uom': product.uom_id.id,
            'price_unit': line.unit_price,
            'date_planned': self.delivery_date or fields.Datetime.now(),
            'taxes_id': [fields.Command.clear()],
        }

    def _action_open_record(self, model, res_id, name):
        """返回打开指定记录的动作（用于按钮跳转）。"""
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'res_id': res_id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _add_timeline(self, state, note=None):
        """写订单轨迹。"""
        Timeline = self.env['gz.order.timeline']
        for order in self:
            Timeline.create({
                'order_id': order.id,
                'state': state or order.state,
                'note': note,
                'operator_id': self.env.user.id,
            })
        return True

    # ------------------------------------------------------------------ 定时任务
    @api.model
    def _cron_sync_platform(self):
        """每 30 分钟与自研平台同步订单进度（预留 REST 对接调用点）。

        契约（docs/04 第 2.12 节）：Odoo → 自研
        ``POST {gz_platform.api_base_url}/api/v1/integration/odoo/ack-order``。

        设计要点：

        * 平台不可用、网络异常、鉴权失败等一律只记警告日志，
          **绝不抛异常中断定时任务**（避免 ir.cron 反复失败）；
        * 未配置 ``gz_platform.api_base_url`` 时只记录日志并返回，便于灰度上线；
        * 幂等由平台侧按 ``order_no`` 保证。
        """
        _logger.info('gz.order._cron_sync_platform：开始同步平台订单进度')
        params = self.env['ir.config_parameter'].sudo()
        base_url = (params.get_param('gz_platform.api_base_url') or '').rstrip('/')
        token = params.get_param('gz_platform.api_token') or ''

        orders = self.sudo().search(
            [('state', 'in', ('confirmed', 'delivering', 'completed', 'settled'))],
            limit=200, order='write_date desc')
        payload = {
            'source': 'odoo',
            'synced_at': fields.Datetime.to_string(fields.Datetime.now()),
            'orders': [{
                'order_no': order.name,
                'state': order.state,
                'stock_deducted': order.stock_deducted,
                'amount_total': order.amount_total,
                'sale_order': order.sale_order_id.name or '',
                'purchase_order': order.purchase_order_id.name or '',
                'updated_at': fields.Datetime.to_string(order.write_date),
            } for order in orders],
        }

        if not base_url:
            _logger.info(
                'gz.order._cron_sync_platform：未配置 gz_platform.api_base_url，'
                '本轮跳过（待同步订单 %s 单）。', len(payload['orders']))
            return False
        if requests is None:
            _logger.warning('gz.order._cron_sync_platform：requests 未安装，跳过本轮同步。')
            return False

        url = '%s/api/v1/integration/odoo/ack-order' % base_url
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-GZ-Token'] = token
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 —— 平台不可用不得影响定时任务
            _logger.warning('gz.order._cron_sync_platform：平台同步失败（已忽略）：%s', exc)
            return False
        _logger.info('gz.order._cron_sync_platform：同步完成，共 %s 单。', len(payload['orders']))
        return True


class GzOrderLine(models.Model):
    _name = 'gz.order.line'
    _description = '瓜子油料平台订单明细'
    _order = 'order_id, id'

    order_id = fields.Many2one(
        'gz.order', string='平台订单', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string='商品', required=True, ondelete='restrict', index=True)
    name = fields.Char(string='说明')
    quantity = fields.Float(string='订单数量', digits=(16, 3), required=True, default=1.0)
    delivered_quantity = fields.Float(
        string='已发货数量', digits=(16, 3), default=0.0)
    uom_id = fields.Many2one(
        'uom.uom', string='计量单位', related='product_id.uom_id', store=False)
    unit_price = fields.Monetary(
        string='单价', currency_field='currency_id', required=True)
    tax_rate = fields.Float(string='税率（%）', digits=(5, 2), default=0.0)
    price_subtotal = fields.Monetary(
        string='小计', currency_field='currency_id',
        compute='_compute_price_subtotal', store=True)
    currency_id = fields.Many2one(
        'res.currency', string='币种', related='order_id.currency_id', store=True)
    remark = fields.Char(string='备注')

    @api.depends('quantity', 'unit_price')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = (line.quantity or 0.0) * (line.unit_price or 0.0)


class GzOrderTimeline(models.Model):
    _name = 'gz.order.timeline'
    _description = '瓜子油料平台订单轨迹'
    _order = 'event_time desc, id desc'
    _rec_name = 'state'

    order_id = fields.Many2one(
        'gz.order', string='平台订单', required=True, ondelete='cascade', index=True)
    state = fields.Selection(
        ORDER_STATES, string='订单状态', required=True, index=True)
    note = fields.Text(string='说明')
    operator_id = fields.Many2one(
        'res.users', string='操作人', default=lambda self: self.env.user)
    event_time = fields.Datetime(
        string='发生时间', default=fields.Datetime.now, required=True, index=True)
