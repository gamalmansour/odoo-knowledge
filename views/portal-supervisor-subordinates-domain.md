# Portal Supervisor Views Missing Subordinates

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-06-17                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `portal`, `domain`, `subordinates`, `supervisor`

---

## Problem

> In custom portal views for supervisors (e.g. tracking sales visits or timesheets), supervisors report that they cannot see the records of their subordinates. They have correctly assigned the `subordinate_ids` via the backend, but the records still do not appear.

## Root Cause

> The portal controller's domain is typically filtering only by a hardcoded relational link (like `plan_line_id.plan_id.supervisor_id = user.id`), neglecting the user's `subordinate_ids` relationship. Because of this, ad-hoc records or records without the explicit supervisor link will not match the domain.

## Solution ✅

> Expand the search domain in the `portal.py` controller to logically OR the specific supervisor link with an `in` check on `user.subordinate_ids.ids`.

```python
# Before
domain = [('plan_line_id.plan_id.supervisor_id', '=', user.id)]

# After
domain = [
    '|', ('plan_line_id.plan_id.supervisor_id', '=', user.id),
         ('salesperson_id', 'in', user.subordinate_ids.ids)
]
```

## ⚠️ Pitfalls

- **Empty subordinate list:** Ensure you handle the case where `user.subordinate_ids.ids` is empty. In Odoo domain syntax, `('salesperson_id', 'in', [])` safely evaluates to false and does not crash, making it safe to use directly.
- **Multiple Controllers:** Remember to update the domains for all related counters (e.g. in `_prepare_home_portal_values`) so that the portal home screen count matches the list view count.

## Verification

> Assign a representative to a supervisor's `subordinate_ids`. Ensure the representative has records that are NOT part of a plan. Login as the supervisor in the portal and verify the records now appear.
