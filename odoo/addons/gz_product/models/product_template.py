# -*- coding: utf-8 -*-
"""瓜子油料商品：扩展 product.template。

字段映射（docs/03 第 9 节）：

    product.code         <-> product.template.default_code
    product.name         <-> product.template.name
    product.spec         <-> gz_spec
    product.grade        <-> gz_grade
    product.origin       <-> gz_origin
    product.harvest_year <-> gz_harvest_year
    product.package      <-> gz_package
    product.enterprise_id<-> gz_enterprise_id

发布规则：``gz_audit_status == 'approved'`` 且质检状态非“不合格”才允许上架，
否则抛 ``UserError``（与自研平台 ``/products/{id}/publish`` 的校验一致）。
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

#: 等级：特级 / 一级 / 二级 / 统货
GZ_GRADES = [
    ('special', '特级'),
    ('first', '一级'),
    ('second', '二级'),
    ('mixed', '统货'),
]

GZ_QUALITY_STATES = [
    ('pending', '待检'),
    ('qualified', '合格'),
    ('unqualified', '不合格'),
]

#: 平台发布状态（对应自研 product.status）
GZ_PUBLISH_STATES = [
    ('draft', '草稿'),
    ('published', '已上架'),
    ('offline', '已下架'),
    ('rejected', '已驳回'),
]

#: 平台审核状态（对应自研 product.audit_status）
GZ_AUDIT_STATES = [
    ('pending', '待审核'),
    ('approved', '审核通过'),
    ('rejected', '审核驳回'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ------------------------------------------------------------------ 归属与规格
    gz_enterprise_id = fields.Many2one(
        'gz.enterprise', string='归属企业', index=True, ondelete='set null',
        tracking=True, help='商品的归属商户 / 供应商，对应自研 product.enterprise_id。')
    gz_spec = fields.Char(string='规格', tracking=True, help='如：千粒重 ≥ 180g')
    gz_grade = fields.Selection(GZ_GRADES, string='等级', index=True, tracking=True)
    gz_origin = fields.Char(string='产地', index=True, help='如：新疆阿勒泰')
    gz_harvest_year = fields.Char(string='年份', size=4, help='如：2025')
    gz_package = fields.Char(string='包装', help='如：50kg 编织袋 / 散装')

    # ------------------------------------------------------------------ 质检与检测报告
    gz_quality_status = fields.Selection(
        GZ_QUALITY_STATES, string='质检状态', default='pending',
        tracking=True, help='与自研 product.quality_status 对齐。')
    gz_test_report = fields.Binary(string='检测报告', attachment=True)
    gz_test_report_filename = fields.Char(string='检测报告文件名')

    # ------------------------------------------------------------------ 溯源与发布
    gz_trace_enabled = fields.Boolean(
        string='启用批次溯源', default=False,
        help='启用后由 gz_inventory 生成批次溯源码。')
    gz_publish_state = fields.Selection(
        GZ_PUBLISH_STATES, string='平台发布状态', default='draft',
        required=True, index=True, tracking=True, copy=False)
    gz_audit_status = fields.Selection(
        GZ_AUDIT_STATES, string='平台审核状态', default='pending',
        required=True, index=True, tracking=True, copy=False)
    gz_audit_remark = fields.Char(string='审核意见', copy=False)
    gz_audit_user_id = fields.Many2one('res.users', string='审核人', readonly=True, copy=False)
    gz_audit_date = fields.Datetime(string='审核时间', readonly=True, copy=False)

    # ------------------------------------------------------------------ 交易参数
    gz_min_order_qty = fields.Float(
        string='起订量', digits=(16, 3), default=0.0,
        help='与自研 product.min_order_qty 对齐，单位与商品计量单位一致。')
    gz_stock_warn_qty = fields.Float(
        string='库存预警值', digits=(16, 3), default=0.0,
        help='gz_inventory 的批次低于该值时进入库存预警。')

    gz_audit_log_ids = fields.One2many(
        'gz.product.audit.log', 'product_tmpl_id', string='平台审核日志')

    # ================================================================== 业务方法
    def action_gz_submit_audit(self):
        """提交平台审核：草稿 / 已驳回的商品可提交。"""
        for tmpl in self:
            if tmpl.gz_audit_status == 'approved' and tmpl.gz_publish_state == 'published':
                raise UserError(_('商品「%s」已上架，无需重复提交审核。') % tmpl.display_name)
            tmpl.write({'gz_audit_status': 'pending', 'gz_audit_remark': False})
            tmpl._gz_log_audit('submit', _('提交平台审核'))
        return True

    def action_gz_audit_approve(self):
        """平台审核通过。"""
        for tmpl in self:
            tmpl.write({
                'gz_audit_status': 'approved',
                'gz_audit_user_id': self.env.user.id,
                'gz_audit_date': fields.Datetime.now(),
            })
            tmpl._gz_log_audit('approve', _('平台审核通过'))
        return True

    def action_gz_audit_reject(self):
        """平台审核驳回：必须填写审核意见。"""
        for tmpl in self:
            if not tmpl.gz_audit_remark:
                raise UserError(_('请先填写「审核意见」并保存，再执行驳回。'))
            tmpl.write({
                'gz_audit_status': 'rejected',
                'gz_publish_state': 'rejected',
                'gz_audit_user_id': self.env.user.id,
                'gz_audit_date': fields.Datetime.now(),
            })
            tmpl._gz_log_audit('reject', tmpl.gz_audit_remark)
        return True

    def action_gz_publish(self):
        """上架：必须已通过平台审核，且质检状态非“不合格”。"""
        for tmpl in self:
            if tmpl.gz_audit_status != 'approved':
                raise UserError(_('商品「%s」未通过平台审核（当前：%s），不能上架。')
                                % (tmpl.display_name, tmpl.gz_audit_status or _('待审核')))
            if tmpl.gz_quality_status == 'unqualified':
                raise UserError(_('商品「%s」质检状态为「不合格」，不能上架。') % tmpl.display_name)
            tmpl.write({'gz_publish_state': 'published'})
            tmpl._gz_log_audit('publish', _('商品上架'))
        return True

    def action_gz_offline(self):
        """下架。"""
        for tmpl in self:
            if tmpl.gz_publish_state != 'published':
                raise UserError(_('只有「已上架」的商品可以下架，商品「%s」当前为：%s。')
                                % (tmpl.display_name, tmpl.gz_publish_state))
            tmpl.write({'gz_publish_state': 'offline'})
            tmpl._gz_log_audit('offline', _('商品下架'))
        return True

    # ================================================================== 内部方法
    def _gz_log_audit(self, action, note=None):
        """写入平台商品审核日志。"""
        Log = self.env['gz.product.audit.log'].sudo()
        for tmpl in self:
            Log.create({
                'product_tmpl_id': tmpl.id,
                'action': action,
                'note': note,
                'operator_id': self.env.user.id,
            })
        return True


class ProductVariant(models.Model):
    _inherit = 'product.product'

    def action_gz_submit_audit(self):
        return self.mapped('product_tmpl_id').action_gz_submit_audit()

    def action_gz_audit_approve(self):
        return self.mapped('product_tmpl_id').action_gz_audit_approve()

    def action_gz_audit_reject(self):
        return self.mapped('product_tmpl_id').action_gz_audit_reject()

    def action_gz_publish(self):
        return self.mapped('product_tmpl_id').action_gz_publish()

    def action_gz_offline(self):
        return self.mapped('product_tmpl_id').action_gz_offline()
