# -*- coding: utf-8 -*-
"""仓储参数 gz.warehouse.config。

对应自研平台 ``warehouse`` / ``storage_location`` 的汇总参数
（docs/03 第 3 节）：库位数、库容（吨）、是否温控。
一个 Odoo 仓库只允许一条配置。
"""

from odoo import fields, models


class GzWarehouseConfig(models.Model):
    _name = 'gz.warehouse.config'
    _description = '瓜子油料平台仓储参数'
    _order = 'warehouse_id, id'
    _rec_name = 'warehouse_id'

    warehouse_id = fields.Many2one(
        'stock.warehouse', string='仓库', required=True,
        ondelete='cascade', index=True)
    enterprise_id = fields.Many2one(
        'gz.enterprise', string='归属企业', index=True,
        help='仓库所属商户 / 供应商；平台公共仓可为空。')
    park_name = fields.Char(
        string='所属园区', help='阶段一占位；阶段二由 gz_park 模块替换为 park_id。')
    warehouse_type = fields.Selection(
        [('own', '自有仓'), ('bonded', '保税仓'), ('temp', '临时仓')],
        string='仓库类型', default='own')
    location_count = fields.Integer(
        string='库位数', default=0, help='与自研 storage_location 记录数对齐。')
    capacity = fields.Float(
        string='库容（吨）', digits=(16, 3), default=0.0)
    temperature_control = fields.Boolean(string='温控仓库', default=False)
    contact_name = fields.Char(string='仓储负责人')
    contact_phone = fields.Char(string='联系电话')
    address = fields.Char(string='仓库地址')
    remark = fields.Text(string='备注')

    _sql_constraints = [
        ('warehouse_uniq', 'unique(warehouse_id)', '一个仓库只能配置一条仓储参数！'),
    ]
