# Building a Client Demo Database: the Four Ordering Traps (Odoo 18)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 17, 18 (verified on 18 EE)                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-08                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `demo-data`, `seeding`, `pre-sales`, `chart-of-accounts`, `l10n`, `product-variants`, `stock-valuation`, `anglo-saxon`, `quality-control`

---

## Problem

A seeded pre-sales demo looks finished and is quietly wrong in four places at once. All four
come from the ORDER the database is built in, and all four are invisible until the client is
in the room:

1. The chart of accounts is the **generic** one (15% tax, 6-digit codes) instead of the
   country's — even though `l10n_xx` is installed.
2. Every product that has variants shows **no internal reference** and **zero cost**, so the
   inventory valuation report reads a fraction of the truth.
3. Stock has no accounting value at all — the P&L shows revenue with **no cost of sales**.
4. After fixing 3, gross margin comes out **negative**:

```
>>> المبيعات            1,815,740.55 EGP
>>> تكلفة المبيعات      1,960,437.41 EGP
>>> مجمل الربح           -144,696.86 EGP  (-8.0%)
```

## Root Cause

| # | Cause |
|---|---|
| 1 | `account` auto-loads a chart at install time from `company.country_id`. No country ⇒ `generic_coa`. Calling `try_loading('eg', …)` afterwards leaves the generic accounts behind. |
| 2 | `default_code` and `standard_price` live on `product.product`, not on `product.template` (`default_code` is related to the single variant; `standard_price` is company-dependent on the variant). A template created WITH a code/cost that later gains an attribute line hands them to nobody — the new variants start empty. |
| 3 | Several localizations (`l10n_eg` among them) ship **no inventory asset accounts**, so `property_stock_valuation_account_id` is empty and categories stay `manual_periodic`. |
| 4 | Under **Continental** accounting a vendor bill debits the expense account directly. A seeded 3-month window that buys more raw material than it consumes therefore books a cost of sales larger than its sales. |

## Solution ✅

Build in this exact order — each step is a precondition of the next:

```bash
# 1. base only, then set the country, THEN the accounting apps
odoo-bin -c demo.conf -d demo -i base --load-language=ar_001 --without-demo=all --stop-after-init
odoo-bin shell -c demo.conf -d demo --no-http <<'PY'
env.company.country_id = env.ref('base.eg')
env.cr.commit()
PY
odoo-bin -c demo.conf -d demo -i l10n_eg,account_accountant,sale_management,purchase,mrp \
         --without-demo=all --stop-after-init        # <- picks l10n_eg by itself
```

```python
# 2. codes and costs belong on the VARIANT, after the attribute lines exist
for v in template.product_variant_ids:
    colour = (v.product_template_variant_value_ids.mapped('name') or [''])[0]
    v.default_code = f"{code}-{SUFFIX[colour]}"
    v.standard_price = round(v.lst_price * cost_ratio, 2)

# 3. create the inventory accounts the localization does not ship, then switch valuation
#    — BEFORE any stock exists; converting afterwards does not revalue what is already there
categ.write({'property_cost_method': 'average', 'property_valuation': 'real_time',
             'property_stock_valuation_account_id': acc_asset.id,
             'property_stock_account_input_categ_id': acc_in.id,
             'property_stock_account_output_categ_id': acc_out.id,
             'property_stock_journal': stock_journal.id})

# 4. Anglo-Saxon, so cost is recognised at delivery at the AVCO price
company.anglo_saxon_accounting = True
```

Full working order: country → apps → identity → products → variant codes → variant costs →
partners → BOMs → **valuation config** → opening stock → transactions → e-invoicing module last.

## ⚠️ Pitfalls

- **Do not "fix" the chart by calling `try_loading` on a company that already has accounts** —
  you end up with both charts. Recreate the database; it is cheaper than explaining 51 orphan
  accounts to the client's accountant.
- **Switching valuation to `real_time` after the opening stock is in creates no layers for it.**
  The balance sheet then shows a fraction of the stock. Configure, then seed.
- **A quality point on a picking type makes `button_validate()` return a wizard**, and
  `quality.check.do_pass()` is a **singleton** method — `checks.do_pass()` raises
  `ValueError: Expected singleton`. Pass the checks one by one before validating:
  ```python
  for check in picking.check_ids.filtered(lambda c: c.quality_state == 'none'):
      check.do_pass()
  ```
- The wizard returned by `button_validate()` / `button_mark_done()` is not always
  `stock.backorder.confirmation` — probe for the method instead of hardcoding `.process()`.
- Install the e-invoicing module (`l10n_eg_edi_eta`, `l10n_sa_edi`, …) **after** seeding, so its
  partner/journal requirements never block a backdated posting.

## Verification

```python
# every one of these must be zero / balanced before the demo is shown
env['product.product'].search_count([('standard_price', '=', 0)])          # 0
env['product.product'].search_count([('default_code', '=', False)])        # 0
env['stock.quant'].search([('location_id.usage','=','internal')]).filtered(lambda q: q.quantity < 0)
# revenue > cost of sales, and debit == credit over all posted moves
```

## Related

- `orm/seeding-demo-transactions-backend-pos-sessions-odoo19.md` — backdating recipes for
  SO/PO/MO/pickings/invoices.
