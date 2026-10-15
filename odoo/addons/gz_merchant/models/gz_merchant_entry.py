# -*- coding: utf-8 -*-
"""商户入驻申请 gz.merchant.entry。

状态机：``draft``（草稿）→ ``submitted``（已提交）→ ``approved`` / ``rejected``。
审核通过后回填企业主体的园区（``park_name``）与档口（阶段一存于本单据，
阶段二由 gz_park 模块接管档口资源模型）。
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

ENTRY_STATES = [
    ('draft', '草稿'),
    ('submitted', '已提交'),
    ('approved', '审核通过'),
    ('rejected', '审核驳回'),
]

#: 允许在界面上直接审核的状态
AUDITABLE_STATES = ('submitted',)


class GzMerchantEntry(models.Model):
    _name = 'gz.merchant.entry'
    _description = '瓜子油料平台商户入驻申请'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'apply_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='申请单号', required=True, copy=False, readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('gz.merchant.entry') or _('New'))
    enterprise_id = fields.Many2one(
        'gz.enterprise', string='申请企业', required=True,
        ondelete='cascade', index=True, tracking=True)
    enterprise_type = fields.Selection(
        related='enterprise_id.enterprise_type', string='企业类型', readonly=True, store=True)
    park_name = fields.Char(
        string='申请园区', tracking=True,
        help='阶段一为文本；阶段二由 gz_park 模块改为 gz.park 关联。')
    stall_code = fields.Char(string='申请档口编号', tracking=True)
    apply_date = fields.Date(
        string='申请日期', required=True, default=fields.Date.context_today)
    applicant = fields.Many2one(
        'res.users', string='申请人', default=lambda self: self.env.user, tracking=True)
    contact_phone = fields.Char(string='联系电话')
    main_products = fields.Char(string='拟经营品类')
    state = fields.Selection(
        ENTRY_STATES, string='状态', default='draft', required=True,
        tracking=True, index=True, copy=False)
    audit_user_id = fields.Many2one('res.users', string='审核人', readonly=True, copy=False)
    audit_date = fields.Datetime(string='审核时间', readonly=True, copy=False)
    audit_remark = fields.Char(string='审核意见')
    remark = fields.Text(string='申请说明')

    _sql_constraints = [
        ('entry_name_uniq', 'unique(name)', '入驻申请单号必须唯一！'),
    ]

    # ================================================================== 默认值
    @api.onchange('enterprise_id')
    def _onchange_enterprise_id(self):
        for rec in self:
            if rec.enterprise_id:
                rec.contact_phone = rec.enterprise_id.contact_phone
                rec.main_products = rec.enterprise_id.main_products
                if not rec.park_name:
                    rec.park_name = rec.enterprise_id.park_name

    # ================================================================== 业务方法
    def action_submit(self):
        """提交入驻申请。"""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('只有「草稿」状态的入驻申请可以提交，当前状态：%s')
                                % dict(ENTRY_STATES).get(rec.state, rec.state))
            rec.write({'state': 'submitted'})
            rec.message_post(body=_('入驻申请已提交，等待园区运营审核。'))
        return True

    def action_approve(self):
        """审核通过：回填企业主体的园区信息。"""
        for rec in self:
            if rec.state not in AUDITABLE_STATES:
                raise UserError(_('只有「已提交」状态的入驻申请可以审核通过，当前状态：%s')
                                % dict(ENTRY_STATES).get(rec.state, rec.state))
            rec.write({
                'state': 'approved',
                'audit_user_id': self.env.user.id,
                'audit_date': fields.Datetime.now(),
            })
            # 园区信息回填：以审核结果为准，使用 sudo 避免操作人无企业主体写权限
            if rec.enterprise_id:
                enterprise = rec.enterprise_id.sudo()
                vals = {}
                if rec.park_name and enterprise.park_name != rec.park_name:
                    vals['park_name'] = rec.park_name
                if vals:
                    enterprise.write(vals)
            rec.message_post(body=_('入驻申请审核通过。'))
        return True

    def action_reject(self):
        """审核驳回：必须填写审核意见。"""
        for rec in self:
            if rec.state not in AUDITABLE_STATES:
                raise UserError(_('只有「已提交」状态的入驻申请可以驳回，当前状态：%s')
                                % dict(ENTRY_STATES).get(rec.state, rec.state))
            if not rec.audit_remark:
                raise UserError(_('请先填写「审核意见」并保存，再执行驳回。'))
            rec.write({
                'state': 'rejected',
                'audit_user_id': self.env.user.id,
                'audit_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('入驻申请驳回：%s') % rec.audit_remark)
        return True

    def action_reset_draft(self):
        """撤回为草稿。"""
        for rec in self:
            if rec.state == 'approved':
                raise UserError(_('已审核通过的入驻申请不能撤回为草稿。'))
            rec.write({'state': 'draft'})
        return True
