# -*- coding: utf-8 -*-
"""平台单据 → Odoo 账务凭证草稿的公共逻辑。

被 ``gz.order`` 与 ``gz.settlement`` 复用（``_inherit`` 抽象模型）：

* 借方 / 贷方科目优先取往来单位上的默认科目（``property_account_receivable_id`` /
  ``property_account_payable_id``），缺失时按科目类型兜底检索；
* 只在草稿态创建 ``account.move``（``move_type = 'entry'``），不做过账，
  过账由财务在 Odoo 中人工确认（符合“自研为源、Odoo 生成凭证草稿”的契约）。
"""

import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GzAccountMoveMixin(models.AbstractModel):
    _name = 'gz.account.move.mixin'
    _description = '瓜子油料平台账务凭证草稿生成'

    def _gz_require_finance_rights(self):
        """生成凭证草稿需要平台管理员或财务角色。"""
        user = self.env.user
        if user.has_group('gz_platform_base.group_gz_platform_admin') \
                or user.has_group('gz_platform_base.group_gz_finance'):
            return True
        raise UserError(_('只有「平台管理员」或「财务」可以生成账务凭证草稿。'))

    def _gz_search_account(self, account_types):
        """按科目类型检索可用科目（跨公司兼容写法，不做 company 过滤）。"""
        return self.env['account.account'].search(
            [('account_type', 'in', list(account_types))], limit=1, order='id')

    def _gz_create_draft_move(self, ref, amount, partner=False, label=None,
                              direction='receivable'):
        """创建账务凭证草稿。

        :param ref: 凭证参考号（订单号 / 结算单号，作为两侧幂等键）
        :param amount: 金额（正数）
        :param partner: 往来单位（``res.partner`` 记录，可空）
        :param label: 分录摘要
        :param direction: ``receivable`` 应收（借：应收 / 贷：收入）、
                          ``payable`` 应付（借：费用 / 贷：应付）
        :return: ``account.move`` 草稿
        """
        self.ensure_one()
        self._gz_require_finance_rights()

        amount = round(amount or 0.0, 2)
        if amount <= 0:
            raise UserError(_('金额必须大于 0 才能生成账务凭证草稿。'))

        company = self.env.company
        journal = self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
        if not journal:
            raise UserError(_('未找到类型为「杂项」(general) 的会计日记账，无法生成凭证草稿。'))

        fallback_partner = company.partner_id
        if direction == 'receivable':
            debit_account = (partner or fallback_partner).property_account_receivable_id \
                or self._gz_search_account(('asset_receivable',))
            credit_account = self._gz_search_account(('income', 'income_other'))
        else:
            debit_account = self._gz_search_account(('expense', 'expense_direct_cost'))
            credit_account = (partner or fallback_partner).property_account_payable_id \
                or self._gz_search_account(('liability_payable',))

        if not debit_account or not credit_account:
            raise UserError(
                _('未找到%s科目，无法生成凭证草稿；请在 Odoo 会计中配置科目表或为往来单位设置默认科目。')
                % (_('应收/收入') if direction == 'receivable' else _('费用/应付')))
        if debit_account == credit_account:
            raise UserError(_('借方与贷方科目相同（%s），请检查科目配置。') % debit_account.display_name)

        line_label = label or ref or _('平台单据')
        move = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'company_id': company.id,
            'date': fields.Date.context_today(self),
            'ref': ref,
            'line_ids': [
                fields.Command.create({
                    'name': line_label,
                    'account_id': debit_account.id,
                    'partner_id': partner.id if partner else False,
                    'debit': amount,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'name': line_label,
                    'account_id': credit_account.id,
                    'partner_id': partner.id if partner else False,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        })
        _logger.info('已生成账务凭证草稿 %s（ref=%s, amount=%s）', move.name, ref, amount)
        return move
