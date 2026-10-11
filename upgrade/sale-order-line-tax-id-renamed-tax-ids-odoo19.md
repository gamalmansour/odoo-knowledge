# `sale.order.line.tax_id` Renamed to `tax_ids` in Odoo 19

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 19                                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-08-02                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `upgrade`, `sale.order.line`, `tax_id`, `tax_ids`, `breaking-change`

---

## Problem

Custom code reading the taxes of a sale order line crashes on Odoo 19:

```
AttributeError: 'sale.order.line' object has no attribute 'tax_id'
```

## Root Cause

The historical (confusingly singular-named) many2many `sale.order.line.tax_id` was renamed to **`tax_ids`** in Odoo 19 (`addons/sale/models/sale_order_line.py`). Same for view domains/contexts referencing it.

## Solution ✅

```python
line_vals['tax_ids'] = [(6, 0, sol.tax_ids.ids)]   # was sol.tax_id
```

Grep before upgrading:

```bash
grep -rn "\.tax_id\b" custom/ --include="*.py" --include="*.xml" | grep -i "sale"
```

Note `account.move.line` still uses `tax_ids`, and `account.tax` relations elsewhere are unaffected — the rename is specifically the SOL field.

## Verification

Hit live in `sale_visit`'s shortfall credit-note feature (Odoo 19): `sol.tax_id` raised AttributeError at runtime (module installed fine — it's a runtime attribute access); caught by the test suite, fixed by the rename, 52/52 green.

## References

- Core: `odoo/addons/sale/models/sale_order_line.py` (`tax_ids = fields.Many2many`)
- Related KB: [product-uom-po-id-removed-odoo19](../orm/product-uom-po-id-removed-odoo19.md), [odoo19_python_signature_changes](odoo19_python_signature_changes.md)
