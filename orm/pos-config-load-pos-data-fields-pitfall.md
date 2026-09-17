# Do Not Override _load_pos_data_fields on pos.config in Odoo 18

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 18.0                                       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-17                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `point_of_sale`, `pos.config`, `_load_pos_data_fields`, `load_data`, `initData`

---

## Problem

When opening Point of Sale in Odoo 18, the screen fails to load and the browser console throws:

```
IndexedDB 1 Ready
point_of_sale.assets_prod.min.js:6101 TypeError: Cannot convert undefined or null to object
    at Object.entries (<anonymous>)
    at Proxy.initData (point_of_sale.assets_prod.min.js:8858:166)
    at async Proxy.setup (point_of_sale.assets_prod.min.js:8833:356)
```

The underlying Python RPC call `pos.session.load_data` fails with:
`KeyError: 'use_pricelist'` (or missing standard fields on `pos.config`).

## Root Cause

In Odoo 18, `pos.config` inherits `pos.load.mixin`, which defaults `_load_pos_data_fields(config_id)` to `[]`.
When `fields` is empty (`[]`), Odoo's ORM `self.search_read(domain, fields, load=False)` automatically loads **ALL** fields of `pos.config` (over 100+ fields, including any custom fields added via `_inherit`).

If a custom module attempts to expose its custom field to POS by overriding `_load_pos_data_fields` on `pos.config`:
```python
# ❌ WRONG
def _load_pos_data_fields(self, config_id):
    params = super()._load_pos_data_fields(config_id)
    if 'my_custom_field' not in params:
        params.append('my_custom_field')
    return params
```
`super()._load_pos_data_fields()` returns `[]`. Appending `'my_custom_field'` converts `fields` from empty (which meant "all fields") to `['my_custom_field']` (which restricts the query to ONLY that field and `id`).
As a result, `pos.config` is read with only `id` and `my_custom_field`, stripping out essential fields like `use_pricelist`, `currency_id`, `name`, etc. `pos.config._load_pos_data` crashes on `data[0]['use_pricelist']`.

## Solution ✅

Do **NOT** override `_load_pos_data_fields` on `pos.config`! Any custom field defined on `pos.config` is automatically fetched and available in `pos.config` on the frontend because `pos.config` loads all fields by default.

```python
# ✅ CORRECT: Simply define the field on pos.config
class PosConfig(models.Model):
    _inherit = 'pos.config'

    whatsapp_receipt_template = fields.Text(string='WhatsApp Receipt Template')
    # No _load_pos_data_fields override needed!
```

## ⚠️ Pitfalls

- Unlike other models (`res.partner`, `product.product`, `pos.order`) where `_load_pos_data_fields` returns an explicit list of field names and you MUST append custom fields, `pos.config` returns `[]` to mean "all fields". Overriding it breaks POS loading completely.

## Verification

Run in Odoo shell:
```python
session = env['pos.session'].search([], limit=1)
config_res = env['pos.config']._load_pos_data({'pos.session': {'data': [{'config_id': session.config_id.id}]}})
assert 'use_pricelist' in config_res['data'][0]
assert 'whatsapp_receipt_template' in config_res['data'][0]
```
