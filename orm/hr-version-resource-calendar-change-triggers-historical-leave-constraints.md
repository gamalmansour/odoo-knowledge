# Changing `resource_calendar_id` on `hr.version` / `hr.employee` Re-evaluates Historical Leaves and Triggers Retroactive Leave Policy Constraints

| Property | Value |
|----------|-------|
| **Category** | `orm` |
| **Severity** | 🔴 Critical |
| **Odoo Versions** | 18, 19 |
| **Tags** | `hr.version`, `hr.employee`, `hr.leave`, `resource_calendar_id`, `hr_holidays`, `constrains`, `base_import` |
| **Last Verified** | 2026-10-28 |

## Problem

When updating an employee's working schedule (`resource_calendar_id`) or contract dates (`contract_date_start`, `contract_date_end`, `date_version`) — either manually on the employee/contract form or via Excel import (`base_import`) — Odoo 19's `addons/hr_holidays/models/hr_version.py` intercepts `write()` and calls `_check_overlapping_contract(leave)` on **all historical leaves** of the employee over the contract period whose `leave.resource_calendar_id != new_resource_calendar_id`.

Inside `_check_overlapping_contract`:
1. `leave.resource_calendar_id = first_overlapping_contract.resource_calendar_id` executes **without** `leave_skip_date_check=True` or `leave_skip_state_check=True`.
2. Dependent overrides (such as `project_timesheet_holidays`) read `leave.number_of_days` inside `hr.leave.write()`, triggering an immediate recomputation of `date_from`, `date_to`, and `number_of_days`.
3. Recomputing `date_from` and `number_of_days` fires custom `@api.constrains` methods on `hr.leave` (e.g., company leave policy limits on consecutive days or monthly caps) as well as `_check_validity()` against historical approved leaves from months or years ago that predate the policy or whose past allocations have expired.

## Solution ✅

1. In `hr.version`, override `create()` and `write()` to inject a context flag (`solargy_skip_leave_policy_check=True`, alongside core's `leave_skip_date_check=True` and `leave_skip_state_check=True`) whenever `resource_calendar_id` or contract dates are modified:

```python
class HrVersion(models.Model):
    _inherit = 'hr.version'

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> models.Model:
        return super(
            HrVersion,
            self.with_context(
                solargy_skip_leave_policy_check=True,
                leave_skip_date_check=True,
                leave_skip_state_check=True,
            ),
        ).create(vals_list)

    def write(self, vals: dict) -> bool:
        if any(
            field in vals
            for field in (
                'contract_date_start',
                'contract_date_end',
                'date_version',
                'resource_calendar_id',
            )
        ):
            self = self.with_context(
                solargy_skip_leave_policy_check=True,
                leave_skip_date_check=True,
                leave_skip_state_check=True,
            )
        return super().write(vals)
```

2. In `hr.leave`, guard custom policy constraints and `_check_validity()` when those context flags are active:

```python
class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.constrains('request_unit_half', 'number_of_days', 'holiday_status_id', 'date_from', 'employee_id')
    def _check_solargy_leave_policy(self) -> None:
        if (
            self.env.context.get('solargy_skip_leave_policy_check')
            or self.env.context.get('leave_skip_date_check')
            or self.env.context.get('leave_fast_create')
        ):
            return
        # ... normal policy enforcement for new/edited leave requests ...

    def _check_validity(self) -> None:
        if self.env.context.get('solargy_skip_leave_policy_check'):
            return
        return super()._check_validity()
```

## ⚠️ Pitfalls

- **In-Place Calendar Rename vs New Calendar Record:** Renaming an existing `resource.calendar` (`ID = 1`) in-place keeps `leave.resource_calendar_id == contract.resource_calendar_id`, so `_get_leaves(extra_domain=[('resource_calendar_id', '!=', resource_calendar_id)])` returns empty and hides the bug in Test. Creating a new `resource.calendar` record or switching an employee to a different shift triggers `_check_overlapping_contract` across all past leaves.
- **Line 130 Context Gap in Core `hr_holidays`:** Core Odoo only applies `with_context(leave_skip_date_check=True, leave_skip_state_check=True)` on line 132 (`_compute_date_from_to()`), AFTER line 130 (`leave.resource_calendar_id = ...`) has already triggered field recomputation and `@api.constrains`. Setting the context in `hr.version.write()` before `super().write(vals)` covers line 130 as well.
