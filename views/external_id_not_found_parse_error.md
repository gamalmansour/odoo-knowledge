---
title: ParseError - ValueError External ID not found (View Loading Order)
date: 2026-06-30
category: views
tags: [xml, parseerror, manifest, data-order, external-id]
odoo_versions: [15.0, 16.0, 17.0]
---

# Problem ❌
When installing or upgrading a module, Odoo throws a `ParseError` with `ValueError: External ID not found in the system`. 
This typically occurs when an XML file (like a form view or a menu item) references an `action` or another `view` using `%(action_id)d` or `ref="module.view_id"`, but Odoo hasn't parsed that target ID yet.

Example Error:
```
ParseError: "External ID not found in the system: construction_project.action_single_project_owl_dashboard"
```

# Cause 🕵️
Odoo loads files linearly based on the order defined in the `data` list inside `__manifest__.py`. If `views/construction_project_views.xml` (which contains the reference to the action) is listed *before* `views/dashboard_action.xml` (which defines the action), Odoo will fail to resolve the ID because it doesn't exist in the database yet.

# Solution ✅
Reorder the `data` array in `__manifest__.py` so that the file defining the ID is listed before the file referencing it.

**Incorrect:**
```python
    'data': [
        'views/construction_project_views.xml', # Uses the action
        'views/dashboard_action.xml',           # Defines the action
    ]
```

**Correct:**
```python
    'data': [
        'views/dashboard_action.xml',           # Defines the action first
        'views/construction_project_views.xml', # Now it can use the action
    ]
```

# ⚠️ Pitfalls
- **Actions before Menus/Views:** Actions must generally be defined before the menus that trigger them, and before the views that reference them in buttons or contexts.
- **Security files:** `security/security_groups.xml` must almost always be loaded *before* `security/ir.model.access.csv`.
- **Inherited Views:** If View B inherits View A within the same module, the file defining View A must appear before the file defining View B.
