# -*- coding: utf-8 -*-
"""企业主体档案 gz.enterprise。

对应自研平台库 ``gz.enterprise``（docs/03-数据模型设计.md 第 2 节“主体域”）：

* Odoo 侧以 ``res.partner`` 作为全平台的往来单位主键，本模型只保存
  “平台主体”特有的字段，并在审核通过后同步到 ``res.partner``；
* ``code``        <-> 自研 ``enterprise.code``  <-> ``res.partner.ref``
* ``unified_social_credit_code`` <-> ``res.partner.vat``

边界约束（docs/02 第 2.2 节“边界防腐措施”）：本模块只使用官方扩展点，
不修改 Odoo 核心；跨模块只通过 ``_inherit`` 与依赖声明协作。
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: 企业类型，与自研平台 enterprise.enterprise_type 取值保持一致
ENTERPRISE_TYPES = [
    ('merchant', '商户'),
    ('supplier', '供应商'),
    ('buyer', '采购商'),
    ('platform', '平台'),
]

AUDIT_STATES = [
    ('pending', '待审核'),
    ('approved', '审核通过'),
    ('rejected', '审核驳回'),
]

ENTERPRISE_STATES = [
    ('active', '启用'),
    ('disabled', '停用'),
]


class GzEnterprise(models.Model):
    _name = 'gz.enterprise'
    _description = '瓜子油料平台企业主体'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code, id'
    _rec_name = 'name'

    # ------------------------------------------------------------------ 基本信息
    name = fields.Char(string='企业名称', required=True, index=True, tracking=True)
    code = fields.Char(
        string='企业编码', required=True, index=True, copy=False, tracking=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('gz.enterprise') or _('New'),
        help='与自研平台 enterprise.code 对齐，由序列 ENT-<年>-<流水号> 生成，'
             '同时写入 res.partner.ref。',
    )
    unified_social_credit_code = fields.Char(
        string='统一社会信用代码', required=True, index=True, copy=False, tracking=True,
        help='平台内唯一，同步写入 res.partner.vat。',
    )
    enterprise_type = fields.Selection(
        ENTERPRISE_TYPES, string='企业类型', required=True, default='merchant',
        index=True, tracking=True,
    )
    legal_person = fields.Char(string='法定代表人')
    registered_capital = fields.Monetary(
        string='注册资本（万元）', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='币种', required=True,
        default=lambda self: self.env.company.currency_id)
    business_scope = fields.Text(string='经营范围')

    # ------------------------------------------------------------------ 联系方式
    contact_name = fields.Char(string='联系人')
    contact_phone = fields.Char(string='联系电话')
    email = fields.Char(string='电子邮箱')
    region = fields.Char(string='行政区划', help='如：新疆·北屯市')
    address = fields.Char(string='详细地址')

    # ------------------------------------------------------------------ 园区
    # 阶段二 gz_park 模块使用 _inherit 追加 park_id（Many2one gz.park），
    # 阶段一先用 Char 占位，避免本模块与 gz_park 产生循环依赖。
    park_name = fields.Char(
        string='所属园区', tracking=True,
        help='阶段一占位字段；阶段二由 gz_park 模块追加 park_id 并回填。')

    # ------------------------------------------------------------------ 平台对接
    platform_code = fields.Char(
        string='平台侧编码', copy=False,
        help='自研平台侧编码缓存；与 code 一致时留空。')
    partner_id = fields.Many2one(
        'res.partner', string='关联往来单位', ondelete='set null',
        index=True, copy=False, tracking=True)
    partner_user_ids = fields.One2many(
        'res.users', string='关联用户', compute='_compute_partner_user_ids',
        help='该往来单位下的 Odoo 用户；企业级数据隔离规则依赖该关联关系。')

    # ------------------------------------------------------------------ 审核与状态
    audit_status = fields.Selection(
        AUDIT_STATES, string='审核状态', default='pending', required=True,
        tracking=True, index=True, copy=False)
    audit_remark = fields.Char(string='审核意见')
    audited_user_id = fields.Many2one('res.users', string='审核人', readonly=True, copy=False)
    audited_date = fields.Datetime(string='审核时间', readonly=True, copy=False)
    status = fields.Selection(
        ENTERPRISE_STATES, string='状态', default='active', required=True,
        tracking=True, index=True)

    remark = fields.Text(string='备注')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', '企业编码必须唯一！'),
        ('unified_social_credit_code_uniq', 'unique(unified_social_credit_code)',
         '统一社会信用代码必须唯一！'),
    ]

    # ================================================================== ORM 扩展
    @api.model_create_multi
    def create(self, vals_list):
        """创建时不足的企业编码由序列补齐（幂等键来自自研平台时以传入值为准）。"""
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('gz.enterprise') or _('New')
        return super().create(vals_list)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.name) if rec.code else (rec.name or '')

    @api.depends('partner_id')
    def _compute_partner_user_ids(self):
        for rec in self:
            rec.partner_user_ids = rec.partner_id.user_ids

    # ================================================================== 业务方法
    def action_approve(self):
        """审核通过：置审核状态并同步往来单位。"""
        for rec in self:
            if rec.audit_status == 'approved':
                continue
            rec.write({
                'audit_status': 'approved',
                'status': 'active',
                'audited_user_id': self.env.user.id,
                'audited_date': fields.Datetime.now(),
            })
            rec._gz_sync_partner()
            rec.message_post(body=_('企业审核通过，已同步往来单位 %s。') % (rec.partner_id.name or ''))
        return True

    def action_reject(self):
        """审核驳回：必须先填写审核意见，驳回后企业置为停用。"""
        for rec in self:
            if not rec.audit_remark:
                raise UserError(_('请先填写「审核意见」并保存，再执行驳回。'))
            rec.write({
                'audit_status': 'rejected',
                'status': 'disabled',
                'audited_user_id': self.env.user.id,
                'audited_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('企业审核驳回：%s') % rec.audit_remark)
        return True

    def action_reset_pending(self):
        """撤回审核结果，回到待审核（仅平台管理员使用）。"""
        for rec in self:
            rec.write({'audit_status': 'pending', 'audit_remark': False})
        return True

    def action_set_active(self):
        self.write({'status': 'active'})
        return True

    def action_set_disabled(self):
        self.write({'status': 'disabled'})
        return True

    def action_sync_partner(self):
        """按钮：创建 / 更新关联 res.partner，并打开该往来单位表单。"""
        self.ensure_one()
        partner = self._gz_sync_partner()
        return {
            'type': 'ir.actions.act_window',
            'name': _('往来单位'),
            'res_model': 'res.partner',
            'res_id': partner.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _gz_sync_partner(self):
        """创建 / 更新关联 res.partner（幂等：优先按 ref 命中已有往来单位）。

        :return: ``res.partner`` 记录
        """
        self.ensure_one()
        Partner = self.env['res.partner'].sudo()
        partner = self.partner_id
        if not partner:
            partner = Partner.search([('ref', '=', self.code)], limit=1)
        if not partner:
            partner = Partner.create({'name': self.name, 'ref': self.code})

        # 商户在平台内既是买方也是卖方，因此两个排名都置 1
        is_supplier = self.enterprise_type in ('supplier', 'merchant', 'platform')
        is_customer = self.enterprise_type in ('buyer', 'merchant', 'platform')
        partner.write({
            'name': self.name,
            'ref': self.code,
            'vat': self.unified_social_credit_code or False,
            'company_type': 'company',
            'phone': self.contact_phone or False,
            'mobile': self.contact_phone or False,
            'email': self.email or False,
            'street': self.address or False,
            'city': self.region or False,
            'comment': self.business_scope or False,
            'supplier_rank': 1 if is_supplier else 0,
            'customer_rank': 1 if is_customer else 0,
        })
        if self.partner_id != partner:
            self.partner_id = partner.id
        _logger.info('gz.enterprise %s 已同步往来单位 res.partner(%s)', self.code, partner.id)
        return partner

    # ================================================================== 辅助
    @api.model
    def _gz_get_user_enterprise(self, user=None):
        """返回当前用户（或指定用户）关联的企业主体记录集。

        供 gz_trade / gz_inventory 等模块在生成单据时取默认企业主体使用。
        """
        user = user or self.env.user
        return self.sudo().search([('partner_id', '=', user.partner_id.id)], limit=1)
