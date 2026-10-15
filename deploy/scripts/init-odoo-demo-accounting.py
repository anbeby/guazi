"""Idempotent minimal Odoo accounting setup for the local Beitun demo.

Run from the project root:
  Get-Content deploy/scripts/init-odoo-demo-accounting.py -Raw |
    docker exec -i gz-api python -

Uses the configured Odoo JSON-RPC identity; does not write to Odoo tables directly.
Creates draft-capable accounts and a general journal, never posts entries.
"""

from app.integrations.odoo_client import odoo_client as odoo


def find_one(model, domain, *, context=None):
    kwargs = {"limit": 1}
    if context:
        kwargs["context"] = context
    ids = odoo.execute_kw(model, "search", [domain], kwargs)
    return ids[0] if ids else None


company_id = find_one("res.company", [])
if company_id is None:
    raise RuntimeError("Odoo company missing")

cny_id = find_one("res.currency", [["name", "=", "CNY"]], context={"active_test": False})
if cny_id is None:
    raise RuntimeError("Odoo CNY currency missing")
odoo.execute_kw("res.currency", "write", [[cny_id], {"active": True}])

company = odoo.execute_kw("res.company", "read", [[company_id]], {"fields": ["currency_id"]})[0]
if company["currency_id"][0] != cny_id:
    odoo.execute_kw("res.company", "write", [[company_id], {"currency_id": cny_id}])

accounts = (
    ("112200", "平台演示应收款", "asset_receivable"),
    ("220200", "平台演示应付款", "liability_payable"),
    ("600100", "平台演示交易收入", "income"),
    ("660100", "平台演示交易成本", "expense"),
)
for code, name, account_type in accounts:
    account_id = find_one("account.account", [["code", "=", code], ["company_id", "=", company_id]])
    if account_id is None:
        account_id = odoo.execute_kw("account.account", "create", [{
            "code": code,
            "name": name,
            "account_type": account_type,
            "company_id": company_id,
            "reconcile": account_type in ("asset_receivable", "liability_payable"),
        }])
    print("account", code, account_id)

journal_id = find_one("account.journal", [["code", "=", "GZJ"], ["company_id", "=", company_id]])
if journal_id is None:
    journal_id = odoo.execute_kw("account.journal", "create", [{
        "name": "瓜子平台演示杂项日记账",
        "code": "GZJ",
        "type": "general",
        "company_id": company_id,
    }])
print("company", company_id, "currency", cny_id, "journal", journal_id)

pricelist_id = find_one("product.pricelist", [["name", "=", "瓜子平台人民币价目表"], ["company_id", "=", company_id]])
if pricelist_id is None:
    pricelist_id = odoo.execute_kw("product.pricelist", "create", [{
        "name": "瓜子平台人民币价目表",
        "currency_id": cny_id,
        "company_id": company_id,
    }])
print("pricelist", pricelist_id)

tax_group_id = find_one("account.tax.group", [["name", "=", "瓜子平台演示税组"], ["company_id", "=", company_id]])
if tax_group_id is None:
    tax_group_id = odoo.execute_kw("account.tax.group", "create", [{
        "name": "瓜子平台演示税组",
        "company_id": company_id,
    }])
print("tax_group", tax_group_id)
country_id = find_one("res.country", [["code", "=", "CN"]])
if country_id is None:
    raise RuntimeError("Odoo China country missing")

for use, name in (("sale", "瓜子平台销售税 9%"), ("purchase", "瓜子平台采购税 9%")):
    tax_id = find_one("account.tax", [["name", "=", name], ["company_id", "=", company_id]])
    if tax_id is None:
        tax_id = odoo.execute_kw("account.tax", "create", [{
            "name": name,
            "type_tax_use": use,
            "amount_type": "percent",
            "amount": 9.0,
            "tax_group_id": tax_group_id,
            "country_id": country_id,
            "company_id": company_id,
        }])
    print("tax", use, tax_id)
