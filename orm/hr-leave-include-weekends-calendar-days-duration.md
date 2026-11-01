# Counting Weekends (Calendar Days) in Leave Duration for Specific Leave Types (e.g., Sick Leave)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-01                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.leave`, `hr.leave.type`, `hr_holidays`, `_get_durations`, `include_weekends_in_duration`, `sick_leave`, `calendar_days`

---

## Problem

> Under Egyptian Labour Law and standard MENA HR policies, **Annual** and **Casual** leaves count working days only (excluding Friday/Saturday weekends), whereas **Sick Leave** (and Maternity Leave) medical certificates span continuous **calendar days** (including Friday and Saturday weekends).
>
> In Odoo `hr_holidays`, `hr.leave._get_durations()` computes `number_of_days` exclusively from the employee's `resource.calendar` working intervals (`_list_work_time_per_day` / `_get_work_days_data_batch`). As a result, a 21-day Sick Leave medical report from `2026-10-29` to `2026-11-18` on a 5-day calendar (`Sun–Thu`) is calculated as **15 days** instead of **21 days**, leaving 6 unconsumed days on the employee's 21-day Sick Leave allocation.
> Enabling `include_public_holidays_in_duration` (`Ignore Public Holidays`) only includes `resource.calendar.leaves` public holidays on working days, not weekly off-days (weekends).

## Root Cause

1. `hr.leave._get_durations()` counts the length of `_list_work_time_per_day()` tuples generated from the employee's `resource.calendar.attendance` lines. Non-scheduled weekdays (Friday/Saturday) have no attendance lines and are always skipped.
2. `hr.leave._compute_duration()` only declares `@api.depends('date_from', 'date_to', 'resource_calendar_id', 'holiday_status_id.request_unit')`, so switching between two day-based leave types (`Annual Leave` -> `Sick Leave`) does not re-trigger `_compute_duration` unless `holiday_status_id` is added to `@api.depends`.
3. Both `number_of_days`, `number_of_hours`, and `duration_display` are stored columns on `hr_leave`.

## Solution ✅

1. Add `include_weekends_in_duration = fields.Boolean(...)` on `hr.leave.type` (declared **before** `HrLeave` in the module load order so `@api.depends('holiday_status_id.include_weekends_in_duration')` resolves cleanly at registry build).
2. Override `_get_durations()` on `hr.leave` to compute inclusive calendar days `(d_to - d_from).days + 1` (and `cal_days * hours_per_day`) when `leave._is_calendar_days_leave()` is `True`.
3. Extend `@api.depends` on `_compute_duration()` to include `'holiday_status_id'`, `'holiday_status_id.include_weekends_in_duration'`, `'request_date_from'`, and `'request_date_to'`.

```python
class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    include_weekends_in_duration = fields.Boolean(
        string='Include Weekends (Calendar Days)',
        default=False,
    )


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def _is_calendar_days_leave(self) -> bool:
        self.ensure_one()
        if not self.holiday_status_id or self.request_unit_hours:
            return False
        if self.holiday_status_id.include_weekends_in_duration:
            return True
        type_name = (self.holiday_status_id.name or '').lower()
        return 'sick' in type_name or 'مرض' in type_name

    def _get_durations(self, check_leave_type: bool = True, resource_calendar=None) -> dict:
        result = super()._get_durations(check_leave_type=check_leave_type, resource_calendar=resource_calendar)
        for leave in self:
            if not leave._is_calendar_days_leave():
                continue
            d_from = leave.request_date_from or (leave.date_from.date() if leave.date_from else False)
            d_to = leave.request_date_to or (leave.date_to.date() if leave.date_to else False)
            if not d_from or not d_to or d_to < d_from:
                continue
            cal_days = (
                0.5
                if (leave.request_unit_half and d_from == d_to and leave.request_date_from_period == leave.request_date_to_period)
                else float((d_to - d_from).days + 1)
            )
            calendar = (
                resource_calendar
                or leave.resource_calendar_id
                or leave.employee_id.resource_calendar_id
                or leave.company_id.resource_calendar_id
            )
            hours_per_day = (calendar.hours_per_day if calendar and calendar.hours_per_day else 8.0)
            result[leave.id] = (cal_days, cal_days * hours_per_day)
        return result

    @api.depends(
        'date_from', 'date_to', 'request_date_from', 'request_date_to',
        'resource_calendar_id', 'holiday_status_id',
        'holiday_status_id.request_unit', 'holiday_status_id.include_weekends_in_duration',
    )
    def _compute_duration(self) -> None:
        super()._compute_duration()
```

## ⚠️ Pitfalls

- **Declare `HrLeaveType` before ALL `HrLeave` inheritances in `models/__init__.py`:** Because `HrLeave._compute_duration` depends on `holiday_status_id.include_weekends_in_duration` AND `HrLeave.init()` queries `hr.leave.type`, if another file in `models/__init__.py` (such as `hr_leave_overtime.py`) inherits `hr.leave` earlier than the file defining `HrLeaveType`, Odoo executes `hr.leave._auto_init()` and `hr.leave.init()` BEFORE `hr.leave.type._auto_init()` creates the `include_weekends_in_duration` column (`UndefinedColumn: column hr_leave_type.include_weekends_in_duration does not exist`). Always import the file defining `HrLeaveType` first, guard column existence with `column_exists` / `create_column` in `HrLeaveType._register_hook()` and `HrLeave.init()`, and queue data migrations via `self.pool.post_init(...)`.
- **Stored `duration_display`:** When recomputing existing `hr.leave` records in `init()` or a migration script, call both `_compute_duration()` and `_compute_duration_display()`, and invalidate `hr.leave.allocation` (`['leaves_taken', 'max_leaves']`).
- **Never fake a 7-day `resource.calendar`:** Changing an employee's working schedule to 7 days/week to make Sick Leave count weekends breaks Annual/Casual leave durations and marks employees absent on Friday/Saturday.

## Verification

- Request a `Sick Leave` from `2026-10-29` to `2026-11-18` for an employee on a 5-day (`Sun–Thu`) schedule -> `number_of_days` is `21.0` (`21 days`).
- Request an `Annual Leave` for the same dates -> `number_of_days` remains `15.0` (`15 days`).

## References

- Related file: `orm/api-depends-on-a-field-declared-in-a-later-module.md`
- Related file: `misc/payroll-30-day-month-invert-basic-not-7day-calendar.md`
