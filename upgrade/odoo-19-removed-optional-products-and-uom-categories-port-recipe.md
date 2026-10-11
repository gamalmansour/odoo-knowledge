# Odoo 19 removed Optional Products (sale.order.option) AND UoM categories — port recipe

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `upgrade`, `sale_management`, `sale.order.option`, `optional-products`, `uom`, `category_id`, `product_uom_id`, `port`, `feature-removal`

---

## Problem

Client asks: "the **Optional Products** tab on the quotation disappeared in
Odoo 19 — bring it back." It is not hidden: Odoo 19 **deleted the whole
feature** — `sale.order.option`, `sale.order.template.option`, their views and
logic are gone from `sale_management` (only stale `.po` strings remain).
Restoring it means re-owning the model in a custom module, and the naive
copy-paste of the v18 files crashes on install.

## Root Cause

Three independent Odoo 19 breaking changes hit the port:

1. **Feature removal** — `sale.order.option` no longer exists anywhere in
   community/enterprise 19; templates lost their options concept too.
2. **UoM categories removed** — `uom.uom` has no `category_id` anymore, so the
   v18 related field crashes at registry setup:
   `KeyError: 'Field category_id referenced in related field definition
   sale.order.option.product_uom_category_id does not exist.'`
   (19 pattern: `allowed_uom_ids = product.uom_id | product.uom_ids` computed
   M2M + domain `[('id','in',allowed_uom_ids)]`; also the decimal precision
   was renamed `Product Unit of Measure` → `Product Unit`.)
3. **Field rename** — `sale.order.line.product_uom` → `product_uom_id`
   (passing the old key in `create()` vals fails).

## Solution ✅

Port the v18 model into a custom module (`solargy_sale_optional_products`)
with these adaptations — everything else survives verbatim
(`technical_price_unit`, `_can_be_edited_on_portal`,
`get_product_multiline_description_sale`, `_compute_price_unit/_discount`
cache-line pricing trick, `action_update_prices` hook, `t-name="card"` kanban):

```python
# v18 -> v19 deltas only:
quantity = fields.Float(digits='Product Unit', ...)          # was 'Product Unit of Measure'
uom_id = fields.Many2one('uom.uom', domain="[('id', 'in', allowed_uom_ids)]", ...)
allowed_uom_ids = fields.Many2many('uom.uom', compute='_compute_allowed_uom_ids')

@api.depends('product_id', 'product_id.uom_id', 'product_id.uom_ids')
def _compute_allowed_uom_ids(self):
    for option in self:
        option.allowed_uom_ids = option.product_id.uom_id | option.product_id.uom_ids

def _get_values_to_add_to_order(self):
    return {..., 'product_uom_id': self.uom_id.id}            # was 'product_uom'
```

View: replace both `product_uom_category_id` (invisible) occurrences with
`allowed_uom_ids`; anchor the page with
`//notebook/page[@name='order_lines']` position="after" on
`sale.view_order_form`. ACLs: salesman rwcu, account readonly/invoice r.

**Report section** (the v18 "Options" table on the printed quotation) ports
verbatim: v18 `sale_management/report/sale_report_templates.xml` inherits
`sale.report_saleorder_document` at `//div[@name='signature']`
position="after" — that anchor still exists in 19. Prints only when
`doc.sale_order_option_ids and doc.state in ['draft', 'sent']`; discounted
options show the original unit price struck through with the net price under
it. Verify by rendering (`_render_qweb_html('sale.report_saleorder', ids)`)
and asserting `table_optional_products` present on a draft with options,
absent after `action_confirm()` and on option-less orders.

## ⚠️ Pitfalls

- **Don't port `sale.order.template.option`** unless the client really uses
  template-driven options — 19 templates have no options concept; the
  template hooks (`_compute_option...`) reference removed plumbing.
- The `_compute_price_unit` cache-line trick (`new()` a sale.order.line, then
  `new_sol.order_id = False`) still works in 19 and is what keeps pricelist
  pricing correct — do not replace it with `list_price`.
- A DB upgraded 18→19 by Odoo has its `sale_order_option` table **dropped** —
  check before promising historical data back (our client's DB: table gone).
- Custom module now OWNS a core-removed model: review it FIRST on the next
  major upgrade (20) — if Odoo reintroduces the feature, map + uninstall.
- Grep any other custom code for `product_uom` on sale.order.line and
  `category_id` on uom — the same two renames break unrelated modules.

## Verification

Fresh-DB `-i solargy_sale_optional_products --test-enable`: 4/4 tests —
precompute (name/uom/pricelist price), add-to-order creates the line and
flips `is_present`, UserError on confirmed orders, options copied with the
quotation. `0 failed, 0 error(s)`.

## Related

- `upgrade/sale-order-line-tax-id-renamed-tax-ids-odoo19.md` (same family of 19 renames)
- `orm/odoo-19-res-groups-category-id-deprecation.md`
- `orm/odoo-19-res-users-groups-id-renamed-group-ids.md`
