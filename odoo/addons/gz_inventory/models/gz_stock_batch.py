# -*- coding: utf-8 -*-
"""平台库存批次 gz.stock.batch。

对应自研平台 ``trace_batch`` / ``inventory`` 的批次维度（docs/03 第 3、6 节）：

* Odoo 侧账实数量以 ``stock.quant`` / ``stock.lot`` 为准，本模型承载
  平台批次号、质检状态、检测报告与溯源码等“平台属性”；
* ``below_warn_qty`` 为库存预警标记：批次数量低于商品上的
  ``gz_stock_warn_qty`` 即进入预警（供「库存预警」菜单过滤）。
"""

from odoo import api, fields, models, _

QUALITY_STATES = [
    ('pending', '待检'),
    ('qualified', '合格'),
    ('unqualified', '不合格'),
]


class GzStockBatch(models.Model):
    _name = 'gz.stock.batch'
    _description = '瓜子油料平台库存批次'
    _inherit = ['mail.thread']
    _order = 'production_date desc, name desc'
    _rec_name = 'name'

    name = fields.Char(
        string='批次号', required=True, copy=False, readonly=True, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('gz.stock.batch') or _('New'))
    product_id = fields.Many2one(
        'product.product', string='商品', required=True,
        ondelete='restrict', index=True, tracking=True)
    product_tmpl_id = fields.Many2one(
        'product.template', string='商品模板', related='product_id.product_tmpl_id',
        store=True, index=True)
    enterprise_id = fields.Many2one(
        'gz.enterprise', string='归属企业', index=True, tracking=True,
        help='批次所属商户 / 供应商；留空表示平台公共库存。')
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='仓库', required=True, index=True, tracking=True)
    location_id = fields.Many2one('stock.location', string='库位')
    lot_ids = fields.One2many(
        'stock.lot', 'gz_batch_id', string='Odoo 批次/序列号')

    production_date = fields.Date(string='生产日期', tracking=True)
    expiry_date = fields.Date(string='有效期至')
    quantity = fields.Float(
        string='批次数量', digits=(16, 3), default=0.0, tracking=True,
        help='平台登记数量；账实数量以 Odoo stock.quant 为准。')
    uom_id = fields.Many2one(
        'uom.uom', string='计量单位', related='product_id.uom_id', store=False)
    quality_status = fields.Selection(
        QUALITY_STATES, string='质检状态', default='pending',
        required=True, index=True, tracking=True)
    test_report = fields.Binary(string='检测报告', attachment=True)
    test_report_filename = fields.Char(string='检测报告文件名')
    trace_code = fields.Char(
        string='溯源码', index=True, copy=False,
        help='溯源二维码内容（如平台公开扫码地址 /api/v1/trace/public/{batch_no}）。')
    origin_base = fields.Char(string='种植基地', help='如：北屯市一八三团种植基地')
    remark = fields.Text(string='备注')

    below_warn_qty = fields.Boolean(
        string='低于库存预警值', compute='_compute_below_warn_qty',
        store=True, index=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', '批次号必须唯一！'),
    ]

    # ================================================================== 计算
    @api.depends('quantity', 'product_id.gz_stock_warn_qty')
    def _compute_below_warn_qty(self):
        for rec in self:
            warn_qty = rec.product_id.gz_stock_warn_qty or 0.0
            rec.below_warn_qty = bool(warn_qty) and rec.quantity < warn_qty

    # ================================================================== 业务方法
    def action_mark_qualified(self):
        """质检合格。"""
        self.write({'quality_status': 'qualified'})
        return True

    def action_mark_unqualified(self):
        """质检不合格（同时禁止该批次商品上架由 gz_product 校验）。"""
        self.write({'quality_status': 'unqualified'})
        return True

    def action_generate_trace_code(self):
        """生成批次溯源码（幂等）。

        采用平台公开扫码地址作为二维码内容：
        ``{平台地址}/api/v1/trace/public/{批次号}``；
        平台地址取 ``ir.config_parameter`` 的 ``gz_platform.public_base_url``。
        """
        params = self.env['ir.config_parameter'].sudo()
        base_url = (params.get_param('gz_platform.public_base_url') or '').rstrip('/')
        for rec in self:
            if rec.trace_code:
                continue
            rec.trace_code = ('%s/api/v1/trace/public/%s' % (base_url, rec.name)
                              if base_url else rec.name)
        return True
