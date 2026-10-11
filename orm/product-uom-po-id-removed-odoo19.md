# `uom_po_id` Removed from product.template in Odoo 19

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `product.template`, `uom`, `uom_po_id`, `uom_ids`, `odoo19`, `upgrade`, `breaking-change`

---

## Problem

Code or data scripts that set the purchase unit of measure crash on Odoo 19:

```
ValueError: Invalid field 'uom_po_id' in 'product.template'
```

## Root Cause

Odoo 19 removed `product.template.uom_po_id` (the separate "Purchase UoM"). The model now has:

- `uom_id` — THE unit of measure (used everywhere including purchases), and
- `uom_ids` — Many2many "Packagings": additional UoMs usable in sales (`domain=[('id','!=',uom_id)]`).

Purchases simply use `uom_id`; the old sale-vs-purchase UoM split is gone (packaging UoMs replace it).

## Solution ✅

```python
# Odoo <= 18
vals = {'uom_id': kg.id, 'uom_po_id': kg.id}
# Odoo 19
vals = {'uom_id': kg.id}                    # purchase uses the same uom
# optional extra sale packagings:
vals = {'uom_id': kg.id, 'uom_ids': [(6, 0, [box_5kg.id])]}
```

## ⚠️ Pitfalls

- Migration scripts / demo generators written for 17-18 will crash on create; grep your codebase
  for `uom_po_id` before an Odoo 19 upgrade (XML data files too).
- To sell weight products at POS (kg with decimal qty), enable the UoM feature:
  `env['res.config.settings'].create({'group_uom': True}).execute()` — kg rounding (0.01)
  already allows decimal quantities in the POS numpad.
