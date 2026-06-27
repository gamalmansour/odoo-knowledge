# resource.calendar: Test a Working Day with `_works_on_date()` in Odoo 19 (not `_get_calendars_attendance_intervals`)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `resource.calendar`, `attendance`, `working-day`, `odoo19`, `upgrade`, `private-method`

---

## Problem

> Custom code calls `resource.calendar._get_calendars_attendance_intervals(start, end, tz)` to decide whether a date is a working day. In Odoo 19 this method does not exist and raises `AttributeError` at runtime — typically the moment a daily/attendance computation runs.

```
AttributeError: 'resource.calendar' object has no attribute '_get_calendars_attendance_intervals'
```

## Root Cause

The method is a **private** core helper. Private methods (leading underscore) are not API-stable and move/rename between versions. The code was written against an older signature; Odoo 19's `resource.calendar` exposes different internals.

## Solution ✅

> To ask "does this schedule work on date X?", use the supported instance method `_works_on_date(date)` — it returns a bool and takes a plain `date`.

```python
# BEFORE (crashes on 19)
tz = rec.resource_calendar_id.tz
intervals = rec.resource_calendar_id._get_calendars_attendance_intervals(
    fields.Datetime.to_datetime(current_date),
    fields.Datetime.to_datetime(current_date + timedelta(days=1)),
    tz,
)
is_working = bool(intervals)

# AFTER (Odoo 19)
is_working = rec.resource_calendar_id._works_on_date(current_date)
```

For richer needs, the real attendance API in 19 is:
- `_attendance_intervals_batch(start_dt, end_dt, resources=None, domain=None, tz=None, lunch=False)` — raw intervals over a window (batch, efficient).
- `get_work_hours_count(start_dt, end_dt, compute_leaves=True, domain=None)` — total working hours.
- `_works_on_date(date)` — bool: is the schedule active on that date.

## ⚠️ Pitfalls

- `_works_on_date` takes a `date`, not a `datetime` — don't wrap it in `fields.Datetime.to_datetime`.
- Looping `_works_on_date` per day is fine for a month; for large ranges prefer one `_attendance_intervals_batch` call over the whole window.
- Any **private** core method call is an upgrade landmine — grep your codebase for `\._[a-z]` calls into core models before each version bump.

## Verification

```bash
# Confirm the method exists in your installed version
grep -n "def _works_on_date" addons/resource/models/resource_calendar.py
# Grep your custom code for the dead method
grep -rn "_get_calendars_attendance_intervals" custom/
```

## References

- Related file: `orm/stored-compute-incomplete-depends-silent-staleness.md`
- Core: `addons/resource/models/resource_calendar.py`
