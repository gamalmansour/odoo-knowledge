# Do Not Override _load_pos_data_fields on pos.config or pos.order in Odoo 18

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 18.0                                       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-17                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `point_of_sale`, `pos.config`, `pos.order`, `_load_pos_data_fields`, `load_data`, `initData`, `taxTotals`

---

## Problem

When opening Point of Sale in Odoo 18, the screen fails to load or crashes immediately with either:

1. **When `pos.config` is overridden:**
```
point_of_sale.assets_prod.min.js: TypeError: Cannot convert undefined or null to object
    at Object.entries (<anonymous>)
    at Proxy.initData (point_of_sale.assets_prod.min.js:8858:166)
```
or `KeyError: 'use_pricelist'`.

2. **When `pos.order` is overridden:**
```
TypeError: Cannot read properties of undefined (reading 'filter')
    at get taxTotals (point_of_sale.assets_prod.min.js:8944:1016)
    at Object.get (point_of_sale.assets_prod.min.js:1055:71)
    at Proxy.get_total_with_tax (point_of_sale.assets_prod.min.js:9007:34)
    at Proxy.getCustomerDisplayData (point_of_sale.assets_prod.min.js:9064:248)
```
(because `this.payment_ids` is `undefined` on `pos.order`).

## Root Cause

In Odoo 18, both `pos.config` and `pos.order` inherit `pos.load.mixin`, which defaults `_load_pos_data_fields(config_id)` to `[]`.
When `fields` is an empty list (`[]`), Odoo's ORM `self.read([], load=False)` or `self.search_read(domain, [], load=False)` automatically loads **ALL** fields of the model (including all custom fields added via `_inherit`).

If a custom module attempts to expose a custom field by overriding `_load_pos_data_fields`:
```python
# ❌ WRONG (for pos.config and pos.order)
def _load_pos_data_fields(self, config_id):
    params = super()._load_pos_data_fields(config_id)
    if 'my_custom_field' not in params:
        params.append('my_custom_field')
    return params
```
`super()._load_pos_data_fields()` returns `[]`. Appending `'my_custom_field'` converts `fields` from empty (which meant "all fields") to `['my_custom_field']` (which tells the ORM to restrict the query to ONLY that field and `id`).

- On `pos.config`: It strips `use_pricelist`, `currency_id`, `name`, etc. → POS initialization crashes.
- On `pos.order`: It strips `payment_ids`, `lines`, `session_id`, etc. → POS order totals (`taxTotals`) crashes because `this.payment_ids` is undefined.

## Solution ✅

Do **NOT** override `_load_pos_data_fields` on `pos.config` or `pos.order`!
Any field defined on `pos.config` or `pos.order` is automatically loaded by the ORM into the POS frontend because both models load all fields (`[]`) by default.

```python
# ✅ CORRECT: Simply define the field on pos.order or pos.config
class PosOrder(models.Model):
    _inherit = 'pos.order'

    access_token = fields.Char(string='Security Token', copy=False)
    # No _load_pos_data_fields override needed!
```

## ⚠️ Pitfalls

- **Model Discrepancy:**
  - Models like `pos.config` and `pos.order` default to `[]` (read all fields). DO NOT override `_load_pos_data_fields` on them.
  - Models like `pos.order.line` and `pos.payment` return explicit lists of field names (`['qty', 'price_unit', ...]`). For those models, you DO need to override and append custom fields.
  - Always check the base implementation in `point_of_sale` before overriding `_load_pos_data_fields`!

## Verification

Run in Odoo shell:
```python
session = env['pos.session'].search([], limit=1)
config_res = env['pos.config']._load_pos_data({'pos.session': {'data': [{'config_id': session.config_id.id}]}})
assert 'use_pricelist' in config_res['data'][0]
assert 'whatsapp_receipt_template' in config_res['data'][0]
```
