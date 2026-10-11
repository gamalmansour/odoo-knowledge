---
title: "Deprecation of name_get in Odoo 17+ (Use _compute_display_name)"
date: 2026-06-29
author: "ENG/Gamal Mansour"
category: "upgrade"
tags:
  - display_name
  - name_get
  - _rec_name
  - odoo17
---

# ⚠️ Deprecation of name_get in Odoo 17+

## 📝 Context
In Odoo 16 and below, developers commonly used the `name_get()` method to customize the display format of a record (e.g., in `Many2one` dropdowns), returning a list of `(id, name)` tuples.

## 💥 Problem / Pitfall
In Odoo 17+, `name_get()` has been deprecated and removed. Attempting to override it will have no effect on the `display_name` used by the framework, leading to fields displaying only the value of `_rec_name` (e.g., just the code instead of `[Code] Description`).

## ✅ Solution
Odoo 17+ introduced `display_name` as a fully functional computed field. You must override the `_compute_display_name` method.

### ❌ Bad (Odoo 16 style)
```python
def name_get(self):
    result = []
    for rec in self:
        name = f"[{rec.code}] {rec.name}" if rec.code else rec.name
        result.append((rec.id, name))
    return result
```

### ✅ Good (Odoo 17+ style)
```python
@api.depends('code', 'name')
def _compute_display_name(self):
    for rec in self:
        rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name
```

## 🔄 6-Month Simulation Risk
If a module is upgraded from V16 to V17+ and still uses `name_get()`, users will silently lose their descriptive dropdowns, causing confusion during data entry and potentially leading to the selection of incorrect records if codes are similar.
