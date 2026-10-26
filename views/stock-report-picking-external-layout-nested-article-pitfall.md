# Adding Company External Layout (`web.external_layout`) to `stock.report_picking` Without Nested `.article` PDF Duplication

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-26                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `qweb`, `report`, `stock.picking`, `report_picking`, `external_layout`, `report_layout`, `article`, `wkhtmltopdf`

---

## Problem

> When users click the primary **Print** button on a `stock.picking` while its status is **Ready** (`state == 'assigned'`), Odoo invokes `do_print_picking` (`stock.action_report_picking` / template `stock.report_picking`) instead of `stock.action_report_delivery` (`Delivery Slip`, which is only bound to the header **Print** button when `state == 'done'`).
> Because `stock.report_picking` in Odoo 17–19 calls `web.report_layout` directly with a bare `<div class="article o_report_layout_standard">` wrapper instead of `web.external_layout`, the printed document has **no company logo, no header, and no footer**.
> Furthermore, naively wrapping `<div class="page">` in `<t t-call="web.external_layout">` without stripping the outer `.article` class causes **every page in the PDF to print twice** and breaks batch multi-company header/footer indexing in `wkhtmltopdf`.

## Root Cause

1. In `addons/stock/views/stock_picking_views.xml`:
   - `state == 'assigned'` (`Ready`) shows `<button name="do_print_picking" string="Print" .../>` which prints `stock.report_picking` (Picking Operations).
   - `state == 'done'` (`Done`) shows `<button name="%(action_report_delivery)d" string="Print" .../>` which prints `stock.report_deliveryslip` (Delivery Slip).
2. In `addons/stock/report/report_stockpicking_operations.xml`, `stock.report_picking` wraps the entire `<t t-foreach="docs" t-as="o">` loop inside a single `<div class="article o_report_layout_standard">` under `<t t-call="web.report_layout">`.
3. In `odoo/addons/base/models/ir_actions_report.py` (`_prepare_html`), Odoo splits the rendered QWeb HTML into `bodies` by querying **all** nodes matching `//div[hasclass('article')]`. Since `web.external_layout` already generates its own `<div class="header">`, `<div class="article" data-oe-model="..." data-oe-id="...">`, and `<div class="footer">` per record `o`, leaving the outer `class="article o_report_layout_standard"` on `stock.report_picking` produces nested `.article` elements — causing `_prepare_html` to extract both the outer container and the inner container as separate PDF bodies.

## Solution ✅

Inherit `stock.report_picking` using QWeb XPath `$0` replacement to wrap `<div class="page">` inside `<t t-call="web.external_layout">$0</t>` while stripping the `article` class from the outer wrapper div and removing the manual page-break paragraph:

```xml
<template id="custom_report_picking_external_layout" inherit_id="stock.report_picking">
    <!-- 1. Strip 'article' class from the outer wrapper to prevent nested .article duplication in _prepare_html -->
    <xpath expr="//div[hasclass('article')]" position="attributes">
        <attribute name="class"></attribute>
    </xpath>
    <!-- 2. Wrap each picking's div.page inside web.external_layout using $0 so child XPaths (e.g. stock_delivery) remain intact -->
    <xpath expr="//div[hasclass('page')]" position="replace">
        <t t-call="web.external_layout">$0</t>
    </xpath>
    <!-- 3. Remove manual page-break paragraph since each external_layout call creates an independent article body -->
    <xpath expr="//p[@style='page-break-after: always;']" position="replace"/>
</template>
```

## ⚠️ Pitfalls

- **Never leave the outer `div.article` class intact when injecting `web.external_layout`:** `ir.actions.report._prepare_html` uses `root.xpath(match_klass.format('article'))` (which matches at any depth `//`). Nested `.article` divs duplicate the entire PDF output and corrupt `header.children[index]` / `footer.children[index]` matching in `minimal_layout`.
- **Use `$0` inside `position="replace"` instead of overriding the full `stock.report_picking` template:** Standard modules like `stock_delivery` (`report_shipping2`) XPath into `//div[@name='div_picking_date']` inside `div.page`. Using `<t t-call="web.external_layout">$0</t>` preserves all inner nodes regardless of module load order.

## Verification

```python
report = self.env['ir.actions.report']._get_report('stock.action_report_picking')
html_content, _ = report._render_qweb_html('stock.action_report_picking', [picking.id])
html_str = html_content.decode('utf-8')
assert f'o_company_{picking.company_id.id}_layout' in html_str
assert html_str.count('data-oe-model="stock.picking"') == 1
```

## References

- `addons/stock/report/report_stockpicking_operations.xml`
- `addons/stock/views/stock_picking_views.xml`
- `odoo/addons/base/models/ir_actions_report.py` (`_prepare_html`)
