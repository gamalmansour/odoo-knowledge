# Sliding Flexible Check-In Window vs Odoo 19 Native `flexible_hours` on `resource.calendar`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `resource.calendar`, `hr_attendance`, `flexible_hours`, `schedule_type`, `lateness`, `early_out`, `sliding_window`, `allowance`

---

## Problem

> A company has employees on a sliding flexible shift (e.g., `08:00–16:00` with a 1-hour flexible arrival window so arriving at `08:00` requires leaving at `16:00`, arriving at `08:30` requires leaving at `16:30`, arriving at `09:00` requires leaving at `17:00`, and arriving after `09:00` incurs lateness from `09:00`).
> Setting Odoo 19's native `schedule_type = 'flexible'` (`flexible_hours = True`) on `resource.calendar` breaks weekday absence detection, loses fixed weekday boundaries (`attendance_ids`), and removes any arrival cutoff.
> Additionally, re-running `_evaluate_late_check_in` inside `hr.attendance.write({'check_out': ...})` when an employee punches out at the end of the day double-consumes the employee's monthly permission allowance if the morning delay was covered by allowance (no penalty record created).

## Root Cause

1. In Odoo 19 (`addons/resource/models/resource_calendar.py`), `schedule_type = 'flexible'` (`flexible_hours = True`) hides and bypasses `attendance_ids` per weekday, treating the calendar as an unanchored weekly hour quota without start/end times or weekday attendance lines.
2. In `hr.attendance.write(vals)`, calling `_evaluate_late_check_in()` when only `check_out` is in `vals` re-evaluates morning delay and consumes from the monthly allowance bucket a second time whenever the first consumption was 100% covered (`penalty_ids` has no `late_in` record).

## Solution ✅

1. Keep `schedule_type = 'fully_fixed'` on `resource.calendar` with standard weekday `attendance_ids` (e.g. `08:00` to `16:00`, Sunday–Thursday) and add `flex_checkin_minutes = fields.Integer(default=0)` on `resource.calendar`.
2. In `hr.attendance._evaluate_attendance_penalties(evaluate_late=True, evaluate_early=True)`:
   - Compute `latest_start_dt = base_start_dt + timedelta(minutes=flex_mins)` and evaluate `late_in_minutes` strictly after `latest_start_dt`.
   - Clamp `effective_start_dt = min(max(punch_in_minute, base_start_dt), latest_start_dt)` and compute `effective_end_dt = effective_start_dt + shift_duration` for `early_out_minutes`.
   - Gate `evaluate_late = 'check_in' in vals` inside `write(vals)` so punching out (`check_out` only) never re-consumes morning lateness allowance.

```python
shift_duration = base_end_dt - base_start_dt
flex_mins = max(0, calendar.flex_checkin_minutes or 0)
latest_start_dt = base_start_dt + timedelta(minutes=flex_mins)

if evaluate_late:
    self._evaluate_late_check_in(check_in_local, latest_start_dt, local_date, tz_name)

if evaluate_early and self.check_out:
    if flex_mins > 0:
        punch_in_minute = check_in_local.replace(second=0, microsecond=0)
        effective_start_dt = min(max(punch_in_minute, base_start_dt), latest_start_dt)
        effective_end_dt = effective_start_dt + shift_duration
    else:
        effective_end_dt = base_end_dt
    self._evaluate_early_check_out(check_out_local, effective_end_dt, local_date, tz_name)
```

## ⚠️ Pitfalls

- **Never enable `flexible_hours = True` (`schedule_type = 'flexible'`)** when HR still requires fixed working days (Sun–Thu), automated absence scanning (`hr.absence`), and a hard morning cutoff (e.g. `09:00 AM`).
- **Clamp `effective_start_dt` at `latest_start_dt` (`09:00`)**: If an employee arrives at `09:20`, they are already penalized `20` minutes for late check-in after `09:00`; clamping `effective_start_dt` to `09:00` sets required check-out to `17:00` instead of `17:20`, preventing double-penalizing the same 20 minutes on departure.
- **Check-out `write()` Idempotency**: Biometric/kiosk attendance creates the record on check-in (`create`) and updates it on check-out (`write({'check_out': ...})`). Only run `_evaluate_late_check_in` when `check_in` is created or modified.

## Verification

```python
# Arrival 08:30, Departure 16:30 on 08:00-16:00 (+60m flex) -> 0 late, 0 early
# Arrival 08:30, Departure 16:00 on 08:00-16:00 (+60m flex) -> 0 late, 30 early
# Arrival 09:15, Departure 17:00 on 08:00-16:00 (+60m flex) -> 15 late, 0 early
```

## References

- Related file: `performance/batch-absence-detection-across-working-calendars.md`
- Related file: `misc/timeoff-counts-weekend-check-resource-calendar.md`
