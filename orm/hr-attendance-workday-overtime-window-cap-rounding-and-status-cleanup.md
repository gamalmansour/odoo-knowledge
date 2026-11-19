# Odoo 19 Workday Overtime Window Clamping, Whole-Hour Flooring, Commercial Rounding, and Stale Status Cleanup

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.attendance`, `hr.attendance.overtime.line`, `hr.version`, `hr.payslip`, `overtime`, `float_round`, `ATTACH_SALARY`

---

## Problem

1. **Inflated Workday Overtime From Early Arrivals, Fractional Minutes, and Approved Leaves:**
   - Core Odoo 19 `hr.attendance.overtime.rule` (`base_off = 'quantity'`, `employer_tolerance = 0`) subtracts `(schedule['work'] - schedule['leave'])` from raw `worked_hours`.
   - For staff whose contract only compensates a fixed morning preparation hour when they complete a full shift inside an authorized window (e.g., `[08:00, 17:00]` on a `09:00–17:00` shift, capped at `1.0h/day`, floored to `60`-minute whole hours), core `quantity` rules inflate overtime with pre-`08:00` arrivals (`07:16`), post-`17:00` minutes (`17:05`), fractional late mornings (`08:11–17:01 = 0.82h`), and partial punches on approved Annual Leave days (`07:16–10:48` where `expected_duration == 0.0h` awards `3.53h` overtime!).
   - Conversely,core `timing` rules (`08:00–09:00`) still award `1.0h` on half-days (`07:16–10:48`) without requiring full 8h shift completion.
2. **Stale `overtime_status = 'to_approve'` When `enable_overtime = False`:**
   - Zeroing `overtime_hours` and `validated_overtime_hours` without clearing `overtime_status = False` and calling `invalidate_recordset(['linked_overtime_ids'])` leaves `'to_approve'` badges stuck on disabled-overtime employees' attendances.
3. **1-Piaster Banker's Rounding Drift (`round(520.625, 2) == 520.62` vs `520.63`):**
   - Python's built-in `round()` uses round-half-to-even, turning `14.0 * 1.5 * (5950 / 30 / 8) = 520.625` into `520.62` instead of commercial `HALF-UP` `520.63` (`odoo.tools.float_utils.float_round`).

## Root Cause

- `hr.attendance.overtime.ruleset` lacks per-contract workday window clamping, checkout grace, lunch subtraction within clamped bounds, daily hour ceiling, and step-minute flooring.
- Newly created `hr.version` records in Odoo 19 default `ruleset_id` to `hr_attendance.hr_attendance_default_ruleset` (`non_work_days` timing rule ONLY — no workday `quantity` rule).
- `hr.attendance.linked_overtime_ids` is a non-stored computed `Many2many`; unlinking or writing `hr.attendance.overtime.line` without `invalidate_recordset(['linked_overtime_ids'])` leaves stale cached lines during `_compute_overtime_status()`.

## Solution ✅

### 1. Clamp Workday Window per `(employee_id, local_date)`, Subtract Scheduled `lunch`, Floor Step Minutes, and Invalidate `linked_overtime_ids`

```python
if daily_cap > 0.0:
    new_duration = min(new_duration, daily_cap)
if step_mins > 0:
    new_duration = math.floor((new_duration * 60.0 + 1e-6) / step_mins) * (step_mins / 60.0)
new_duration = round(new_duration, 4)

if new_duration <= 0.0:
    if lines:
        lines.unlink()
elif lines:
    keep_line = lines[-1]
    if len(lines) > 1:
        lines[:-1].unlink()
    keep_line.write({'duration': new_duration, 'manual_duration': new_duration})
else:
    OvertimeLine.create({
        'employee_id': emp.id,
        'date': local_date,
        'time_start': target_att.check_in,
        'time_stop': target_att.check_out,
        'duration': new_duration,
        'manual_duration': new_duration,
        'amount_rate': 1.5,
    })

to_recompute.invalidate_recordset(['linked_overtime_ids'])
to_recompute._compute_overtime_hours()
to_recompute._compute_expected_hours()
to_recompute._compute_validated_overtime_hours()
to_recompute._compute_overtime_status()
```

### 2. Commercial `HALF-UP` Rounding on Payslip Overtime & Upgrade Protection for Orphan `ATTACH_SALARY` Lines

```python
from odoo.tools.float_utils import float_round

raw_ovt_amount = (weekday_ovt_hours * hourly_rate * 1.5) + (offday_ovt_hours * hourly_rate * 2.0)
total_ovt_amount = float_round(raw_ovt_amount, precision_digits=2)
```

## ⚠️ Pitfalls

- **Isolate overtime-only contract writes from penalty recalculation (`action_recalculate_overtime_policy` vs `action_recalculate_attendance_policy`):** Calling `action_recalculate_attendance_policy()` when HR only toggles `enable_overtime` or `overtime_workday_window_only` on `hr.version` re-evaluates historical `late_in`/`early_out` penalties across all months, resurrecting `1–4` minute `early_out` deductions that HR intentionally cleared during payroll reconciliation.
- **Odoo 19 `Default Ruleset` (`id=1`) has NO workday rule:** Core `hr.version.ruleset_id` defaults to `Default Ruleset` (`timing_type = 'non_work_days'` only). Because `ver.ruleset_id` is truthy (`1`), `if not ver.ruleset_id:` never assigns a workday `quantity` ruleset! Check `any(r.base_off == 'quantity' or r.timing_type == 'work_days' for r in ver.ruleset_id.rule_ids)` AND allow `_apply_solargy_workday_overtime_policy()` to create `hr.attendance.overtime.line` directly when `use_window` yields `new_duration > 0`.
- **Group same-day split punches by `(employee_id, local_date)` and do NOT clamp `24.0` to `23:00`:** Build window/lunch bounds via `local_tz.localize(datetime.combine(local_date, time.min) + timedelta(minutes=int(round(hour_float * 60))))` instead of `dt.replace(hour=min(h, 23), ...)` so `24.0` resolves to next-day midnight and `pytz` DST offsets stay accurate.
- **Guard `0.0` float window bounds (`is not False and is not None`):** Never write `ver.overtime_window_start or 8.0`, because `0.0` (`00:00` midnight) is falsy in Python and would silently turn into `08:00`.
- **Protect orphan `ATTACH_SALARY` / `ASSIG_SALARY` / `CHILD_SUPPORT` lines on module upgrade:** If HR closes an `hr.salary.attachment` after computing a draft payslip, Odoo removes the backing `hr.payslip.input` while leaving the computed `hr.payslip.line`. Skip automatic upgrade-time `compute_sheet()` on slips where `_has_orphan_salary_line()` is `True`.
- **Batch `related='current_version_id.<field>'` writes in `HrEmployee.write()`:** Odoo's ORM `_inverse_related` writes one field at a time onto `current_version_id`. Changing `[08:00, 17:00]` to `[17:00, 22:00]` on `hr.employee` otherwise flushes a transient `start == 17.0, end == 17.0` state on the first field write and crashes with `@api.constrains` `ValidationError` (while also triggering `N` redundant recalculations). Forward all policy fields in a single `versions.write(policy_vals)` call.
- **Preserve `'refused'` and `'approved'` `hr.attendance.overtime.line` statuses across policy recalculation (`solargy_preserve_overtime_decisions`) and refresh draft payslips on `HrAttendanceOvertimeLine.write()`:** Core `HrAttendance._update_overtime()` unlinks all overtime lines and recreates them as `'to_approve'` when `attendance_overtime_validation == 'by_manager'`, which silently resurrects refused overtime into payroll and drops `validated_overtime_hours` to `0.0` during policy recalculation.
- **Distribute workday overtime across `reversed(day_atts)` capped at each punch's `worked_hours` & use `_attendance_intervals_batch(win_start, win_end)` for cross-midnight windows:** Dumping 100% of `new_duration` onto `day_atts[-1]` produces negative `expected_hours` (`worked_hours - overtime_hours < 0`) when the final split punch is shorter than `new_duration`, and summing only `in_local.date()` `day_lines` on an overnight shift (`Sun 22:00–24:00` + `Mon 00:00–06:00`) undercounts the 8h shift as 2h.

## Verification

```bash
/Users/gamal/.pyenv/versions/3.11.9/bin/python3 /Users/gamal/odoo/odoo19.0/odoo-bin \
  -c /Users/gamal/odoo/odoo19.0/solargy.conf \
  -d solargy_test_clone \
  --data-dir=/tmp/solargy_test_clone_data \
  --http-port=8099 --gevent-port=8098 \
  --test-enable --test-tags /solargy_hr --stop-after-init
```

## References

- Related file: `orm/odoo19-api-depends-on-non-stored-relational-field-trigger-crash.md`
- Related file: `orm/hr-attendance-penalty-dual-mission-audit-notes-and-session-cap.md`
