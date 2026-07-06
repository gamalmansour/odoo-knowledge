---
title: "HR Leave Allocation: 'You can't do the same action twice' on bulk approval"
description: "Fixing double-action error when writing to state='validate' on hr.leave.allocation due to _check_approval_update throwing exceptions."
author: "ENG/Gamal Mansour"
date: "2026-07-06"
tags: ["orm", "hr_holidays", "allocation", "validation", "state", "UserError"]
versions: ["16", "17", "18", "19"]
---

# HR Leave Allocation: 'You can't do the same action twice' on bulk approval

## 🔴 Problem
When implementing custom bulk approvals for `hr.leave.allocation` (e.g., allocating to a department or company), overriding `action_approve` to automatically advance the state to `'validate'` can cause a `UserError: "You can't do the same action twice."` if the state is already validated.

This happens because standard Odoo's `_check_approval_update` method validates state transitions. If you execute:
```python
alloc.write({'state': 'validate'})
```
when `alloc.state` is already `'validate'`, `_check_approval_update` is triggered and strictly blocks it for non-superusers, causing the user experience to break (especially if they click Approve twice due to UI refresh delays or invisible smart buttons).

Also, if the smart button showing the child allocations uses `invisible="not solargy_child_allocation_ids"`, Odoo might not evaluate it properly, making the user think nothing happened and click Approve again.

## ✅ Solution

1. **Guard the state update:** Always check the current state before writing to `state` in an `action_approve` override.
```python
if alloc.state != 'validate':
    alloc.write({
        'state': 'validate', 
        'approver_id': self.env.user.employee_id.id,
        'second_approver_id': self.env.user.employee_id.id
    })
```

2. **Fix the Smart Button Invisible condition:** Do not use `invisible="not solargy_child_allocation_ids"` for One2many fields. Instead, use a computed integer field for the count, and evaluate against `0`.
```python
solargy_child_allocation_count = fields.Integer(compute='_compute_child_allocation_count')

@api.depends('solargy_child_allocation_ids')
def _compute_child_allocation_count(self):
    for alloc in self:
        alloc.solargy_child_allocation_count = len(alloc.solargy_child_allocation_ids)
```
```xml
<button name="action_view_child_allocations" type="object" class="oe_stat_button" icon="fa-users"
        invisible="solargy_child_allocation_count == 0">
    <field name="solargy_child_allocation_count" widget="statinfo" string="Allocations"/>
</button>
```

## ⚠️ Pitfalls
- **Superuser testing:** Testing as `SUPERUSER` or via `odoo-bin shell` will bypass `_check_approval_update` because it starts with `if self.env.is_superuser(): return True`. Always test approval workflows as a normal standard user (e.g., HR Manager).
- **Multiple Clicks:** Without the state guard, users will get a cryptic error instead of a silent no-op.
