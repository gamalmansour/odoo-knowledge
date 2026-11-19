# Flexible-Shift Morning Excuse Shift-Back & Midday Overlap Non-Double-Counting in `hr.attendance`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.attendance`, `hr.leave`, `hr.attendance.penalty`, `flexible-shift`, `flex_checkin_minutes`, `early_out`, `midday-overlap`, `solargy_hr`

---

## Problem

On a working schedule with a sliding flexible check-in window (e.g., `Shift (2) 8:00 to 16:00 (+60 Flexible)`, `flex_checkin_minutes = 60`), an employee who arrives inside the flexible window with an approved morning `hr.leave` excuse gets penalized with a false **Early Departure (`early_out`)** deduction:

- **Example 1:** Schedule `08:00–16:00 (+60m flex)`. Employee punches `08:04 → 16:03` with an approved `08:00–08:04` (`4m`) morning excuse. Because `08:04 <= 09:00`, morning lateness is `0`, so the `4m` excuse is never consumed. The sliding-window formula sets `effective_end_dt = 08:04 + 8h = 16:04`, while `_get_approved_excuse_minutes(..., 'early_out')` ignores morning excuses ending before `13:00` → **`early_out_minutes = 1`** → false `0.25`-day (`quarter_day`) deduction.
- **Example 2:** Schedule `08:00–16:00 (+60m flex)`. Employee punches `08:25 → 16:07` with an approved `10:00–11:30` (`90m`) morning excuse → `effective_end_dt = 16:25` → false **`early_out_minutes = 18`** (`0.50`-day deduction).

Conversely, naively crediting morning excuses onto the flexible shift start without tracking midday overlap leaves creates a **double-counting loophole**: an hourly leave such as `11:30–14:00` (`150m`, `h_from <= 12.0`, `h_to >= 13.0`, `12.5 <= midpoint < 13.5`) satisfies **both** `late_in` and `early_out` classifiers and would be credited once to shift `effective_start_dt` back and a second time against `early_out`.

## Root Cause

1. `_evaluate_attendance_penalties()` computed `effective_start_dt = min(max(punch_in_minute, base_start_dt), latest_start_dt)` solely from the raw punch timestamp without crediting unused approved morning excuses/permissions (`morning_excuse_mins - min(late_past_cutoff, morning_excuse_mins)`).
2. `_get_approved_excuse_details()` returned total minutes without separating `overlap_mins` from hourly leaves that qualify for both `late_in` and `early_out` (or non-interval fallback hourly leaves that apply unconditionally to both sides).

## Solution ✅

1. Add `_get_approved_excuse_breakdown(local_date, penalty_type)` returning `(total_excuse_mins, perm, details, overlap_mins)` (with `_get_approved_excuse_details()` and `_get_approved_excuse_minutes()` delegating to it for backward compatibility):
   - Track `overlap_mins += mins` for hourly leaves where `applies_late and applies_early` (`h_from <= 12.0 and midpoint < 13.5` **and** `h_to >= 13.0 and midpoint >= 12.5`, excluding full-day `mins >= 420` leaves), plus partial (`0 < mins < 420`) non-interval fallback hourly leaves (`elif leave.number_of_hours > 0:`).
   - Treat 7+ hour (`mins >= 420`) non-interval fallback hourly leaves (`request_hour_from/to = 0.0` or `NULL`) identically to interval full-day missions (`total_excuse_mins += 1440`, `overlap_mins += 0`), and skip zero-minute rounded entries (`mins == 0`) so audit details stay clean.
2. In `_evaluate_attendance_penalties()`, credit unused morning excuse minutes back onto `effective_start_dt` (clamped at `base_start_dt`) and pass `overlap_consumed_mins` to `_evaluate_early_check_out()`:

```python
late_past_cutoff = max(0, int((check_in_local - latest_start_dt).total_seconds() // 60))
morning_excuse_mins, _perm, _details, morning_overlap_mins = (
    self._get_approved_excuse_breakdown(local_date, 'late_in')
)
non_overlap_morning_mins = max(0, morning_excuse_mins - morning_overlap_mins)
late_excuse_used = min(late_past_cutoff, morning_excuse_mins)

if flex_mins > 0:
    punch_in_minute = check_in_local.replace(second=0, microsecond=0)
    raw_effective_start = min(max(punch_in_minute, base_start_dt), latest_start_dt)
    unused_morning_excuse = max(0, morning_excuse_mins - late_excuse_used)
    effective_start_dt = max(
        base_start_dt,
        raw_effective_start - timedelta(minutes=unused_morning_excuse),
    )
    flex_credited_mins = max(
        0, int((raw_effective_start - effective_start_dt).total_seconds() // 60)
    )
    effective_end_dt = effective_start_dt + shift_duration
else:
    flex_credited_mins = 0
    effective_end_dt = base_end_dt

total_morning_used = late_excuse_used + flex_credited_mins
overlap_consumed_mins = min(
    morning_overlap_mins,
    max(0, total_morning_used - non_overlap_morning_mins),
)
self._evaluate_early_check_out(
    check_out_local,
    effective_end_dt,
    local_date,
    tz_name,
    overlap_consumed_mins=overlap_consumed_mins,
)
```

3. Inside `_evaluate_early_check_out(..., overlap_consumed_mins: int = 0)`:

```python
excuse_mins, perm, excuse_details = self._get_approved_excuse_details(local_date, 'early_out')
if overlap_consumed_mins > 0:
    excuse_mins = max(0, excuse_mins - overlap_consumed_mins)
    excuse_details = list(excuse_details) + [
        _("-%(mins)s mins already credited to morning/flex", mins=overlap_consumed_mins)
    ]
```

## ⚠️ Pitfalls

- **Always clamp `effective_start_dt` at `base_start_dt`:** A 90-minute morning excuse (`10:00–11:30`) with an `08:25` check-in on an `08:00–16:00` shift must shift `effective_start_dt` back to `08:00` (`effective_end_dt = 16:00`), never to `06:55` (`14:55`).
- **Consume non-overlap morning excuses before midday overlap leaves:** Computing `overlap_consumed_mins = min(morning_overlap_mins, max(0, total_morning_used - non_overlap_morning_mins))` ensures a morning-only permission/excuse is used before touching a midday overlap leave's remaining afternoon minutes.
- **Do not run month-wide `action_recalculate_attendance_policy()` during targeted live remediation:** `action_recalculate_attendance_policy()` re-evaluates *every* attendance in the employee's calendar month and can resurrect historical unapplied penalties that HR deliberately deleted during payroll reconciliation. For targeted remediation of specific attendances, invoke `att._evaluate_attendance_penalties(evaluate_late=True, evaluate_early=bool(att.check_out))` only on the affected `hr.attendance` IDs.
- **Subtract `late_past_cutoff` before computing `unused_morning_excuse`:** Prevents post-cutoff arrivals (e.g., `09:20` with a `30m` excuse on `08:00–16:00 +60m`) from double-dipping the same `20m` once against `late_in` and again against the sliding shift start.
- **Apply the `mins >= 420` Full-Day check in the non-interval fallback branch too:** Legacy or imported hourly leaves/missions with `request_hour_from = 0.0, request_hour_to = 0.0` (or `NULL`) and `number_of_hours >= 7.0` must grant `1440` mins (`overlap_mins = 0`), not raw `420`/`480` mins in `overlap_mins`; otherwise an employee stopping by the office briefly on a full-day hourly mission receives a false `0.50`-day penalty. Also guard `elif mins > 0:` so multi-day tiny-hour records rounding to `0` mins never append `(0 mins)` noise to `notes`.

## Verification

```bash
# Run targeted flexible-shift morning excuse & midday overlap test on an isolated clone DB:
odoo-bin -c solargy.conf -d solargy_test \
  --test-enable \
  --test-tags /solargy_hr:TestAttendancePolicy.test_35_flexible_shift_morning_excuse_prevents_false_early_out \
  --stop-after-init --max-cron-threads=0 --http-port=8029
```

## References

- Related file: `orm/hr-attendance-penalty-dual-mission-audit-notes-and-session-cap.md`
- Module implementation: `solargy_hr/models/hr_attendance.py` (`_get_approved_excuse_breakdown`, `_evaluate_attendance_penalties`, `_evaluate_early_check_out`)
