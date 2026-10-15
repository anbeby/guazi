"""Reconcile existing local demo orders and settlement drafts against Odoo.

Run from I:\\瓜子:
  Get-Content deploy/scripts/reconcile-odoo-demo-orders.py -Raw |
    docker exec -i gz-api python -
Only updates Odoo draft order currency/tax metadata through JSON-RPC.
"""

from decimal import Decimal

from app.core.database import get_session_factory
from app.integrations.odoo_client import odoo_client as odoo
from app.models.settlement import Settlement
from app.models.trade import TradeOrder


def one(model, domain, fields):
    rows = odoo.execute_kw(model, "search_read", [domain], {"fields": fields, "limit": 2})
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one {model} for {domain}, got {len(rows)}")
    return rows[0]


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


currency = one("res.currency", [["name", "=", "CNY"]], ["name"])["id"]
pricelist = one("product.pricelist", [["name", "=", "瓜子平台人民币价目表"]], ["currency_id"])["id"]
sale_tax = one("account.tax", [["name", "=", "瓜子平台销售税 9%"]], ["amount"])["id"]
purchase_tax = one("account.tax", [["name", "=", "瓜子平台采购税 9%"]], ["amount"])["id"]

session = get_session_factory()()
try:
    orders = session.query(TradeOrder).order_by(TradeOrder.id).all()
    for order in orders:
        if order.currency != "CNY" or money(order.tax_amount) != money(order.amount) * Decimal("0.09"):
            raise RuntimeError(f"Unexpected currency/tax rate: {order.order_no}")
        sale = one("sale.order", [["client_order_ref", "=", order.order_no]],
                   ["order_line", "state", "pricelist_id"])
        purchase = one("purchase.order", [["partner_ref", "=", order.order_no]],
                       ["order_line", "state"])
        if sale["state"] != "draft" or purchase["state"] != "draft":
            raise RuntimeError(f"Cannot modify non-draft order: {order.order_no}")
        if len(sale["order_line"]) != len(order.items) or len(purchase["order_line"]) != len(order.items):
            raise RuntimeError(f"Line count mismatch: {order.order_no}")
        if not sale["pricelist_id"] or sale["pricelist_id"][0] != pricelist:
            odoo.execute_kw("sale.order", "write", [[sale["id"]], {"pricelist_id": pricelist}])
        odoo.execute_kw("purchase.order", "write", [[purchase["id"]], {"currency_id": currency}])
        if sale["order_line"]:
            odoo.execute_kw("sale.order.line", "write", [sale["order_line"], {"tax_id": [[6, 0, [sale_tax]]]}])
            odoo.execute_kw("purchase.order.line", "write", [purchase["order_line"], {"taxes_id": [[6, 0, [purchase_tax]]]}])
        for model, domain in (
            ("sale.order", [["id", "=", sale["id"]]]),
            ("purchase.order", [["id", "=", purchase["id"]]]),
        ):
            row = one(model, domain, ["amount_untaxed", "amount_tax", "amount_total", "currency_id"])
            if (money(row["amount_untaxed"]) != money(order.amount)
                    or money(row["amount_tax"]) != money(order.tax_amount)
                    or money(row["amount_total"]) != money(order.total_amount)
                    or row["currency_id"][0] != currency):
                raise RuntimeError(f"Amount/currency mismatch: {model} {order.order_no}: {row}")

    settlements = session.query(Settlement).order_by(Settlement.id).all()
    for settlement in settlements:
        move = one("account.move", [["ref", "=", settlement.settlement_no]],
                   ["amount_total", "currency_id", "state", "line_ids"])
        if move["state"] != "draft" or move["currency_id"][0] != currency:
            raise RuntimeError(f"Settlement state/currency mismatch: {settlement.settlement_no}")
        if money(move["amount_total"]) != money(settlement.settle_amount):
            raise RuntimeError(f"Settlement amount mismatch: {settlement.settlement_no}")
        lines = odoo.execute_kw("account.move.line", "read", [move["line_ids"]],
                                {"fields": ["debit", "credit"]})
        if sum(money(x["debit"]) for x in lines) != sum(money(x["credit"]) for x in lines):
            raise RuntimeError(f"Unbalanced settlement draft: {settlement.settlement_no}")
    print(f"RECONCILED orders={len(orders)} sales={len(orders)} purchases={len(orders)} "
          f"settlement_drafts={len(settlements)} currency=CNY tax=9%")
finally:
    session.close()
