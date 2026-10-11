# Two-Way HR Employee and Res Users Supervisor Sync with Cycle Prevention and Team Scoping

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.employee`, `res.users`, `supervisor`, `hierarchy`, `sync`, `cycle-prevention`, `team-scoping`, `ir.rule`

---

## Problem

When managing sales representatives or field agents under supervisors in Odoo, clients frequently report that "entering an employee under their manager is not working" or that supervisors cannot see their assigned representatives across operational screens (Visits, Plans, Orders, Targets, Commissions).

Specifically:
1. **Coupling Disconnect:** Setting a manager on `hr.employee.parent_id` did not update `res.users.supervisor_ids` or `subordinate_ids`, and vice-versa, causing confusion between HR and Sales configurations.
2. **Restrictive Domains:** Custom user fields (like `subordinate_ids`) often restrict the domain to specific representative types (e.g. `domain="[('representative_type', 'in', ...)]"`), silently hiding new or unclassified employees from the supervisor selection list.
3. **Hidden Hierarchy Fields:** View visibility conditions like `invisible="representative_type in ('supervisor', False)"` prevent managers from being assigned on user cards until secondary fields are configured.
4. **Missing "My Team" Filters:** Operational search views only provided "My Records" (`[('salesperson_id', '=', uid)]`), which returned 0 results for supervisors because supervisors do not execute the visits/orders themselves.
5. **Infinite Recursion / Recursion Storms:** Naive synchronization hooks between `res.users` and `hr.employee` create infinite write recursion loops without context recursion guards.

---

## Root Cause

1. `hr.employee` and `res.users` represent two distinct entities in Odoo: the physical/organizational employee and the system user login. Without bi-directional synchronization, organizational structure defined in HR is completely invisible to business workflow logic built on `res.users`.
2. Operational models link to `salesperson_id` or `user_id` (`res.users`). If supervisors rely on search filters or record rules that only check direct ownership (`user.id`), supervisors cannot view their team's documents without elevated administrative privileges.
3. Many2many relations on `res.users` (supervisor $\leftrightarrow$ subordinate) can easily suffer from circular references (A manages B, B manages A), creating infinite loops during recursive hierarchy resolution (`all_subordinate_ids`).

---

## Solution ✅

### 1. Robust Two-Way Synchronization with Recursion Guards

Hook into both `res.users.write()`, `res.users.create()`, and `hr.employee.write()`, guarded by `context.get('skip_manager_sync')`:

```python
# In models/hr_employee.py
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def write(self, vals):
        res = super().write(vals)
        if 'parent_id' in vals and not self.env.context.get('skip_manager_sync'):
            self._sync_user_supervisors()
        return res

    def _sync_user_supervisors(self):
        for employee in self:
            if not employee.user_id:
                continue
            user = employee.user_id
            manager_user = employee.parent_id.user_id if employee.parent_id else False
            if manager_user:
                if manager_user not in user.supervisor_ids:
                    user.with_context(skip_manager_sync=True).write({
                        'supervisor_ids': [Command.link(manager_user.id)]
                    })
            else:
                user.with_context(skip_manager_sync=True).write({
                    'supervisor_ids': [Command.clear()]
                })
```

In `res.users`, ensure changes to `subordinate_ids` sync the manager on affected subordinate employees (both old and newly assigned):

```python
# In models/res_users.py
def write(self, vals):
    old_subordinates = self.browse()
    if 'subordinate_ids' in vals and not self.env.context.get('skip_manager_sync'):
        old_subordinates = self.mapped('subordinate_ids')

    res = super().write(vals)
    if ('supervisor_ids' in vals or 'subordinate_ids' in vals) and not self.env.context.get('skip_manager_sync'):
        affected_users = self | old_subordinates | self.mapped('subordinate_ids')
        affected_users._sync_hr_employee_managers()
    return res
```

### 2. Multi-Hop Cycle Prevention via Depth-First Search

Prevent users from assigning themselves as supervisors, and detect any circular reference upward or downward:

```python
@api.constrains('subordinate_ids', 'supervisor_ids')
def _check_supervisor_subordinate_cycle(self) -> None:
    for user in self:
        if user in user.subordinate_ids or user in user.supervisor_ids:
            raise ValidationError(_("A user cannot be their own supervisor."))
        # Downward cycle check
        visited_sub = set()
        stack_sub = list(user.subordinate_ids.ids)
        while stack_sub:
            curr_id = stack_sub.pop()
            if curr_id == user.id:
                raise ValidationError(_("Circular supervisor-subordinate relationship detected."))
            if curr_id not in visited_sub:
                visited_sub.add(curr_id)
                sub_user = self.browse(curr_id)
                stack_sub.extend(sub_user.subordinate_ids.ids)
```

### 3. Cross-Module "My Team" Search Filters and Scoping

Add team search filters across operational models so supervisors can easily isolate their team's records:

```xml
<!-- Visits -->
<filter string="My Team's Visits" name="my_team_visits"
        domain="[('salesperson_id.supervisor_ids', '=', uid)]"/>

<!-- Plans -->
<filter string="My Team's Plans" name="my_team_plans"
        domain="['|', ('supervisor_id', '=', uid), ('salesperson_id.supervisor_ids', '=', uid)]"/>

<!-- Sales Orders -->
<filter string="My Team's Orders" name="my_team_sale_orders_filter"
        domain="[('user_id.supervisor_ids', '=', uid)]"/>

<!-- Targets -->
<filter string="My Team's Targets" name="my_team_targets"
        domain="[('salesperson_id.supervisor_ids', '=', uid)]"/>
```

---

## ⚠️ Pitfalls

1. **Many2many Asymmetry on Write:** When `supervisor.write({'subordinate_ids': ...})` is called, `self` is the supervisor, not the subordinate. You must explicitly resolve `self.subordinate_ids` (and `old_subordinates`) to locate the actual employee records that need `parent_id` synchronization.
2. **Infinite Recursion:** Never call `write()` across models in an inverse or synchronization hook without passing a context flag like `with_context(skip_manager_sync=True)`.
3. **Odoo 19 Field Renaming:** In Odoo 19, user groups are linked via `group_ids`, not `groups_id`. Using `groups_id` raises `ValueError: Invalid field 'groups_id' in 'res.users'`.
4. **ORM Cache Invalidation:** If record rules or dynamic domains depend on `subordinate_ids`, override `_get_invalidation_fields()` on `res.users` to include `{'subordinate_ids', 'supervisor_ids'}` so rule caches invalidate immediately upon assignment.

---

## Verification

1. Create a user and corresponding `hr.employee`.
2. Assign manager on `hr.employee` $\rightarrow$ verify `res.users.supervisor_ids` updates automatically.
3. Assign subordinate on `res.users` $\rightarrow$ verify `hr.employee.parent_id` updates automatically.
4. Attempt mutual supervision (A supervises B, B supervises A) $\rightarrow$ verify `ValidationError` is raised.
5. Log in as supervisor $\rightarrow$ verify "My Team's Visits" and "My Team's Orders" filter returns team records.
