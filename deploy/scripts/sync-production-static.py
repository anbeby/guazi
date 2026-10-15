"""Build production-only static HTML without local demo login hints.

This copies the current mobile UI from source, so product UI changes are not
lost behind the production bind mount. It does not touch business data.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "services" / "api" / "app" / "static"
TARGET = ROOT / "deploy" / "conf" / "production-static"


def replace_once(content: str, before: str, after: str) -> str:
    count = content.count(before)
    if count != 1:
        raise ValueError(f"Expected one match, found {count}: {before[:60]}")
    return content.replace(before, after, 1)


for page in ("m", "console"):
    html = (SOURCE / page / "index.html").read_text(encoding="utf-8")
    if page == "m":
        html = replace_once(html, 'id="u" value="jinsui"', 'id="u" value=""')
        html = replace_once(html, 'id="p" type="password" value="Gz@123456"', 'id="p" type="password" value=""')
        html = replace_once(
            html,
            '<details class="muted" style="font-size:12px;margin-top:14px;line-height:1.9"><summary>查看演示账号</summary>供应商 jinsui · 商户 fengyuan · 采购商 gongxiao<br />演示密码 Gz@123456</details>',
            '<p class="muted" style="font-size:12px;margin-top:14px;line-height:1.9">请联系平台管理员领取商户或采购商账号。</p>',
        )
    else:
        html = replace_once(html, 'id="loginPass" name="password" type="password" value="Admin@123"', 'id="loginPass" name="password" type="password" value=""')
        html = replace_once(
            html,
            '''    <div class="tip">
      演示账号：<br />
      平台管理员 <b>admin / Admin@123</b><br />
      园区运营 <b>park01 / Gz@123456</b>　供应商 <b>jinsui / Gz@123456</b><br />
      商户 <b>fengyuan / Gz@123456</b>　采购商 <b>gongxiao / Gz@123456</b>
    </div>''',
            '    <div class="tip">请联系平台管理员领取账号。</div>',
        )
    output = TARGET / page / "index.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(output)
