---
tags: [upgrade, python, odoo19, signatures, prepare_procurement_values]
category: upgrade
description: Python method signature changes in Odoo 19 (e.g. _prepare_procurement_values)
---

# 📝 Python Method Signature Changes in Odoo 19

**Date:** 2026-07-05
**Author:** ENG/Gamal Mansour
**Odoo Versions:** 19.0
**Module/Area:** Base/Sale/Stock

## ❌ The Problem
When calling or overriding certain core Python methods in Odoo 19, you might encounter a `TypeError: ... takes 1 positional argument but 2 were given` or similar errors. This happens because Odoo 19 changed the signature of various methods, removing optional parameters that were used in previous versions.

**Example Error Trace:**
```python
TypeError: SaleOrderLine._prepare_procurement_values() takes 1 positional argument but 2 were given
```

## ✅ The Solution
Review the method signature in the Odoo 19 core modules and update your custom module overrides to match the new signature. Do not pass parameters to `super()` if they are no longer accepted.

### Example: `_prepare_procurement_values` in `sale.order.line`
**Odoo 18 and below:**
```python
def _prepare_procurement_values(self, group_id=False):
    res = super()._prepare_procurement_values(group_id)
    # Custom logic
    return res
```

**Odoo 19:**
```python
def _prepare_procurement_values(self):
    res = super()._prepare_procurement_values()
    # Custom logic
    return res
```

## ⚠️ Pitfalls & Risks (6-Month Pre-mortem)
- **Silent Failures:** If your code passes keyword arguments that are `**kwargs` in the parent method, the error might not appear, but the argument might be ignored by the parent method in Odoo 19.
- **Multiple Addons Override:** If multiple custom modules override the same method and one of them hasn't updated its signature, it could break the whole method chain. Ensure all third-party modules are also updated.

## 🔗 References
- Odoo 19 Source Code: `addons/sale_stock/models/sale_order_line.py`
