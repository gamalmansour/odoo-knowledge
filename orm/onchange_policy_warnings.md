---
title: Implementing Policy-Based UI Warnings in Odoo via @api.onchange
category: ORM
tags: [onchange, warning, ux, policy]
odoo_version: 17.0
last_verified: 2026-07-02
---

# Problem
You need to warn users immediately in the UI when their input violates a company policy (like quantity limits or budget limits), but the actual blocking/enforcement is done later in the workflow (e.g., upon confirmation).

# Solution ✅
Use `@api.onchange` to return a `warning` dictionary. This triggers a standard Odoo warning dialog without preventing the user from saving the draft record.

```python
    @api.onchange('quantity_executed')
    def _onchange_quantity_executed(self):
        # Validate conditions...
        policy = self.project_id.profile_id.qty_control_policy
        if policy in ('warn', 'block'):
            if projected_qty > allowed_qty:
                return {
                    'warning': {
                        'title': _('Quantity Warning'),
                        'message': _('You exceeded the allowed quantity.')
                    }
                }
```

# ⚠️ Pitfalls
1. **New vs Existing Records**: In an `onchange` method, `self.id` is not always set (it might be a NewId).
2. **Translation**: Always wrap `title` and `message` in `_()` so they are correctly translated to the user's language.
3. **Blocking**: `onchange` cannot block a user from saving. True constraints should still be placed in `create`, `write`, or action methods to ensure data integrity.
