# -*- coding: utf-8 -*-
"""原生批次/序列号 stock.lot 的平台扩展。

把 Odoo 的 ``stock.lot``（账实批次）挂接到平台批次 ``gz.stock.batch``，
并冗余质检状态与溯源码，便于库存界面直接查看。
"""

from odoo import fields, models

QUALITY_STATES = [
    ('pending', '待检'),
    ('qualified', '合格'),
    ('unqualified', '不合格'),
]


class StockLot(models.Model):
    _inherit = 'stock.lot'

    gz_batch_id = fields.Many2one(
        'gz.stock.batch', string='平台批次', ondelete='set null', index=True,
        help='Odoo 批次对应的平台批次记录。')
    gz_quality_status = fields.Selection(
        QUALITY_STATES, string='平台质检状态', default='pending', index=True)
    gz_trace_code = fields.Char(
        string='平台溯源码', copy=False,
        help='与 gz.stock.batch.trace_code 一致，供扫码溯源使用。')

    def action_gz_sync_from_batch(self):
        """从平台批次同步质检状态与溯源码。"""
        for lot in self:
            batch = lot.gz_batch_id
            if not batch:
                continue
            lot.write({
                'gz_quality_status': batch.quality_status,
                'gz_trace_code': batch.trace_code,
            })
        return True
