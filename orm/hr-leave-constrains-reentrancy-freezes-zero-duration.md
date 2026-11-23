# `@api.constrains` Re-Entrancy on `hr.leave` Freezes `number_of_days = 0` When Editing Leave Type and Dates Together

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-23                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.leave`, `constrains`, `re-entrancy`, `is_protected`, `number_of_days`, `0 days`, `_compute_date_from_to`, `_compute_duration`, `hr_holidays`

---

## Problem

When a custom `@api.constrains` on `hr.leave` constrains both an upstream field (`request_unit_half` / `holiday_status_id`) and a downstream computed field (`date_from`, `number_of_days`), editing **both** `holiday_status_id` and `request_date_from`/`request_date_to` in the same `write()` (for example, changing a Saturday weekend-inclusive leave into a weekday-only Casual Leave spanning Thu–Sun) silently stores **`number_of_days = 0` and `number_of_hours = 0`** even though `date_from` and `date_to` update to the new dates.

- First approval (manager `action_approve` → `state='validate1'`) succeeds because core `hr_holidays` only checks `_get_leaves_on_public_holiday()` on final validation (`_action_validate`).
- Final HR validation then crashes with:

```
odoo.exceptions.ValidationError: The following employees are not supposed to work during that period:
 <Employee Name>
```

## Root Cause

`hr.leave` has a multi-level stored compute dependency chain:

1. Level 0 (inputs): `holiday_status_id`, `request_date_from`, `request_date_to`
2. Level 1 (computed): `request_unit_half` (`_compute_request_unit_half`, depends on `holiday_status_id`)
3. Level 2 (computed): `date_from`, `date_to` (`_compute_date_from_to`, depends on `request_unit_half`, `request_date_from`, `request_date_to`)
4. Level 3 (computed leaf): `number_of_days`, `number_of_hours` (`_compute_duration`, depends on `date_from`, `date_to`, `holiday_status_id`)

When `write()` updates `holiday_status_id` + `request_date_from` + `request_date_to` together:
1. Odoo queues all dependent stored fields into `env.transaction.tocompute` upfront and runs `_validate_fields()`.
2. The custom constraint reads `rec.date_from`, entering `_compute_date_from_to()` with `env.protecting([date_from, date_to], rec)`.
3. Mid-flight inside `_compute_date_from_to()` (before `date_from`/`date_to` are written with the new dates), Odoo reads `holiday.request_unit_half`, triggering `_compute_request_unit_half()` followed immediately by `_validate_fields(['request_unit_half'])`.
4. The custom constraint re-enters mid-flight and reads `rec.number_of_days`. Because `date_from`/`date_to` are protected, they still hold the **old** timestamps (e.g. Saturday), so `_compute_duration()` runs prematurely on the stale weekend dates, writes `0.0`, and **pops `number_of_days` out of `tocompute`**.
5. `_compute_date_from_to()` then finishes writing the new `date_from`/`date_to`, but `number_of_days` was already popped from `tocompute` and is never recomputed again.

## Solution ✅

Guard the `@api.constrains` loop per record with `self.env.is_protected(...)` on `date_from` and `date_to` so the premature mid-flight re-entrant frame is skipped. Once `_compute_date_from_to()` finishes and unprotects `date_from`/`date_to`, Odoo immediately calls `_validate_fields(['date_from', 'date_to'])` (and resumes the outer constraint frame), running `_compute_duration()` once on the final dates and enforcing every policy rule accurately:

```python
@api.constrains('request_unit_half', 'number_of_days', 'holiday_status_id', 'date_from', 'employee_id')
def _check_custom_leave_policy(self) -> None:
    date_from_field = self._fields['date_from']
    date_to_field = self._fields['date_to']
    for rec in self:
        if (
            self.env.is_protected(date_from_field, rec)
            or self.env.is_protected(date_to_field, rec)
        ):
            continue
        if not rec.employee_id or not rec.holiday_status_id or not rec.date_from:
            continue
        # Safe to read rec.number_of_days and enforce all leave policy rules here
```

## ⚠️ Pitfalls

- **Never skip on the whole recordset (`self`) at once:** In batch `write()` calls, check `self.env.is_protected(field, rec)` per record inside the loop so unprotected siblings are still validated immediately.
- **Keep `'date_from'` in `@api.constrains(...)`:** That guarantees Odoo invokes the constraint again right after `_compute_date_from_to()` finishes writing and unprotecting `date_from`/`date_to`, so zero policy checks are ever bypassed.
- **Hidden policy bypass before the fix:** Because the stale computation yielded `number_of_days = 0`, upper-bound constraints (such as max 2 consecutive casual days) could also be silently bypassed when editing a weekend leave into a 3-day casual leave in one save.

## Verification

1. Create a weekend-inclusive leave (`include_weekends_in_duration=True`) on Saturday (`number_of_days == 1.0`).
2. In a single `write()`, change `holiday_status_id` to a weekday-only Casual Leave and change `request_date_from`/`request_date_to` to Thu–Sun → assert `number_of_days == 2.0` and `number_of_hours == 16.0`.
3. Repeat with Thu–Mon (3 working days) → assert `ValidationError` is raised by the 2-day Casual Leave cap.

## References

- Core compute & constraint flow: `addons/hr_holidays/models/hr_leave.py` (`_compute_date_from_to`, `_compute_request_unit_half`, `_compute_duration`)
- ORM protection API: `odoo/orm/environments.py` (`Environment.is_protected`)
