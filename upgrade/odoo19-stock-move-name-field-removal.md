# Odoo 19: stock.move 'name' Field Removed

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 19.0                                       |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-10-06                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo19`, `stock`, `stock.move`, `upgrade`, `migration`, `tests`

---

## Problem

When upgrading or writing unit tests, wizards, or integrations creating `stock.move` records in Odoo 19:
```python
move = env['stock.move'].create({
    'name': 'Custom Move Description',
    'product_id': product.id,
    'product_uom_qty': 10.0,
    ...
})
```
Odoo raises a blocking error:
```
ValueError: Invalid field 'name' on model 'stock.move'
```

## Root Cause

In Odoo 19, the legacy `name` char field on `stock.move` was removed.
The model now relies on:
1. `display_name` (computed from `product_id.display_name`).
2. `description_picking` and `description_picking_manual` for picking document and line-level descriptions.
Attempting to supply `'name'` in `create()` or `write()` vals triggers an invalid field exception during cache update (`_update_cache`).

## Solution ✅

Remove `'name'` from `stock.move` creation dictionaries. If a specific description is needed, use `description_picking`:

```python
# Odoo 19 syntax
move = env['stock.move'].create({
    'product_id': product.id,
    'product_uom': product.uom_id.id,
    'product_uom_qty': 10.0,
    'location_id': src_loc.id,
    'location_dest_id': dest_loc.id,
    'description_picking': 'Optional custom note', # instead of 'name'
})
```

## ⚠️ Pitfalls

- **Unit Tests and Fixtures:** Pre-Odoo 19 tests almost universally include `'name': product.name` or `'name': '/'` in move values. All such test definitions fail when executed against Odoo 19.
- **Reporting:** QWeb templates referencing `move.name` will raise `AttributeError`. Use `move.product_id.display_name` or `move._get_report_description_picking()`.

## Verification

Run test cases creating `stock.move`:
```bash
python3 odoo-bin shell -c solargy.conf -d solargy --no-http << 'EOF'
move = env['stock.move'].create({
    'product_id': env['product.product'].search([], limit=1).id,
    'product_uom_qty': 1.0,
    'location_id': 1,
    'location_dest_id': 2,
})
print("Move created with ID:", move.id)
EOF
```

## References

- Core definition: `addons/stock/models/stock_move.py`
