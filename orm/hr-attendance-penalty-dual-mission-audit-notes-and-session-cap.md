# HR Attendance Penalty Audit Breakdown, 1.00-Day Session Cap, and Targeted XML/Attendance Remediation in Odoo 19

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.attendance`, `hr.attendance.penalty`, `hr.payslip`, `hr.leave`, `missions`, `convert_file`, `payroll-audit`

---

## Problem

1. **Opaque Same-Day Dual Deductions (`0.25 + 0.25`):** When an employee has two partial hourly `Missions` or `Excuses` (`hr.leave` with `request_unit_hours = True`) on the same working day—for example, a morning mission `09:00–10:31` with check-in at `10:36` (`5m` uncovered = `0.25d`) and an afternoon mission `14:00–17:00` with check-out at `13:53` (`7m` uncovered = `0.25d`)—the payslip displays a combined `LATE_DED` amount and two penalty lines with blank `notes` and hidden timing/coverage columns, causing HR to question every month why the day was deducted twice.
2. **Uncapped Same-Session `late_in + early_out` Exceeding `1.00` Day:** Without a per-session cap across `late_in` and `early_out`, arriving late (`0.50d` or `1.00d`) and leaving early (`1.00d`) on the same attended session deducts `1.25`–`2.00` days (exceeding a full day's wage despite attending work). Furthermore, partial re-evaluations (`evaluate_late=True, evaluate_early=False`) can leave an existing `early_out` penalty uncapped when `late_in` increases.
3. **Live Remediation Blast-Radius Traps:**
   - Calling `action_recalculate_attendance_policy()` on one attendance record re-evaluates **all** attendances in that calendar month, resurrecting penalties on other dates that HR intentionally cleared during payroll reconciliation.
   - Running a full `-u <module>` merely to ship XML view columns triggers `HrPayslip.init()` across all open `draft` payslips, wiping manual/orphan `hr.payslip.line` entries (such as historical `ATTACH_SALARY` rows without backing inputs).

## Root Cause

- `_get_approved_excuse_minutes()` only returned `(total_minutes, perm[:1])` (dropping exact `hr.leave` / `hr.attendance.permission` IDs, intervals, and extra standalone permissions on the same day), and penalty `create()` left `notes` empty.
- `_evaluate_late_check_in()` and `_evaluate_early_check_out()` computed penalty tiers independently with no session-level `1.00`-day ceiling.
- `hr_payslip_views.xml` omitted `planned_time_str`, `actual_time_str`, `covered_by_allowance`, and `notes` from the `attendance_penalty_ids` inline list.

## Solution ✅

### 1. Itemize Excuses/Missions in `_get_approved_excuse_details()` & Enforce the `1.00`-Day Session Cap

```python
# Sum all approved standalone permissions on the date (not limit=1) and itemize all approved leaves:
excuse_mins, perm, excuse_details = self._get_approved_excuse_details(local_date, 'early_out')
covered = min(total_early, excuse_mins)
uncovered = max(0, total_early - covered)

# Safeguard: combined late_in + early_out on one attended session cannot exceed 1.00 day (ignore waived)
same_att_late_days = sum(
    self.penalty_ids.filtered(
        lambda p: p.penalty_type == 'late_in' and p.state != 'waived'
    ).mapped('deduction_days')
)
remaining_cap = max(0.0, round(1.0 - same_att_late_days, 2))
capped_note = ''
if ded_days > remaining_cap:
    capped_note = _(
        " | Capped from %(raw).2f to %(capped).2f day(s) (1.00/day max)",
        raw=ded_days,
        capped=remaining_cap,
    )
    ded_days = remaining_cap
if ded_days <= 0.0:
    return  # Do NOT create a 0.00-day draft row (which Reset-to-Draft would inflate back to 1.00d)
```

Also re-sync existing unapplied `early_out` penalties whenever `evaluate_late=True` runs on an attendance that already has `check_out`:

```python
has_unapplied_early_pen = any(
    p.penalty_type == 'early_out' and p.state not in ('applied', 'waived')
    for p in self.penalty_ids
)
if (evaluate_early or (evaluate_late and has_unapplied_early_pen)) and self.check_out:
    self._evaluate_early_check_out(check_out_local, effective_end_dt, local_date, tz_name)
```

### 2. Apply XML Views & Remediate a Single Attendance on Live Without Side Effects (Odoo 19)

```python
from odoo.tools.convert import convert_file

# Note: `kind` argument is deprecated in Odoo 19 — omit it.
for xml_rel in (
    'views/hr_payslip_views.xml',
    'views/hr_attendance_penalty_views.xml',
    'views/hr_attendance_views.xml',
):
    convert_file(env, 'solargy_hr', xml_rel, {}, mode='update')

# Re-evaluate ONLY the target attendance (never action_recalculate_attendance_policy() on reconciled months)
att = env['hr.attendance'].sudo().browse(791)
att._evaluate_attendance_penalties(evaluate_late=True, evaluate_early=True)
env['hr.payslip'].sudo().browse(198)._refresh_draft_payslip_sheets()
```

## ⚠️ Pitfalls

- **Never create `0.00`-day `draft` penalty rows when `remaining_cap == 0.0`, and enforce the `1.00`-day cap across `(employee_id, date)` in `_recalculate_tier_penalty()` & `action_waive()`:**
  - If `action_reset_draft()` recomputes from raw `uncovered_minutes` without checking non-waived same-day sibling penalties (and custom `solargy.attendance.penalty.tier` rows), confirming and resetting a `0.50`-day capped penalty inflates the session to `1.50` days while `notes` still says `Capped from 1.00 to 0.50 day(s)`.
  - Conversely, when `action_waive()` waives a `1.00`-day `late_in` penalty on an attendance whose `early_out` was suppressed by the cap, `action_waive()` must update the waived note to `(Waived).` and re-evaluate `early_out` on that attendance/date so the early departure deduction is not silently lost.
  - Scoping the `1.00`-day ceiling to `(employee_id, local_date)` (not just `self.penalty_ids`) also prevents split/duplicate same-day biometric `hr.attendance` sessions from deducting `2.00` days on a single attended workday.
- **Clear `early_out_minutes` and unapplied `early_out` penalties when `check_out` becomes `False`:** Never gate early-out cleanup solely behind `if ... and self.check_out:`; otherwise clearing an erroneous `check_out` punch leaves a phantom `early_out` penalty attached and bypasses the `1.00`-day cap.
- **Retroactive `hr.attendance.permission` convergence (`create`/`write`/`unlink`):** Standalone `hr.attendance.permission` records approved, refused, reset, edited, or deleted *after* the biometric punch was recorded must trigger `hr.attendance` penalty re-evaluation and refresh overlapping `draft`/`verify` payslips just like `hr.leave`.
- **Non-HR employee & Attendance Manager `AccessError` traps on `hr.attendance`:**
  - Add `compute_sudo=True` on `hr.attendance.penalty_count` and gate `<notebook groups="hr.group_hr_user">` around `<field name="penalty_ids">` on `hr.attendance` form view; otherwise regular employees (`hr_attendance.group_hr_attendance_officer` without `hr.group_hr_user`) crash with `AccessError` opening their own Attendances list/form view.
  - Use `.sudo()` inside `HrAttendance` automated penalty/permission/absence evaluation because `hr.attendance.penalty` write/create/unlink ACLs are restricted to `hr.group_hr_manager`, whereas Attendance Managers (`hr_attendance.group_hr_attendance_manager`) and HR Officers (`hr.group_hr_user`) legitimately create/edit/recalculate attendances.
- **Python `0.0 in (False, None, '')` truthiness trap on float hours:** Because `0.0 == False` in Python, `0.0 not in (False, None, '')` evaluates to `False`! Always check `raw_from is not False and raw_from is not None and raw_from != ''` so midnight `00:00` (`0.0`) hourly leaves keep their interval and do not leak into `early_out`.
- **Odoo 19 OWL `ListRenderer` (`column_width_hook.js`) 1-million numeric width trap:** Unconstrained numeric columns inside narrow form sheets (with right-side chatter open on `1440px` screens) reserve space for `1,000,000` (~95px each), pushing `notes` off-screen or squeezing it into an 80px column. Set explicit compact `width="46px"`–`"66px"` on minute/day/time columns and `width="235px" class="text-wrap"` on `notes`.
- **Do not clamp `24.0` to `23:00` when formatting float hours for display:** Helpers built for `datetime.replace(hour=..., minute=...)` clamp `min(hour, 23)`, turning `24.0` into `23:00`. Use a dedicated display formatter `divmod(max(0, int(round(hour_float * 60))), 60)` for `HH:MM` interval strings.
- **Core `hr_payroll_holidays` updates `hr.leave.write_date` during `compute_sheet()`:** Recomputing a payslip updates `payslip_state` on `hr.leave` records in that period; when snapshotting leaves around `compute_sheet()`, compare functional fields (`state`, dates, `request_hour_from`, `request_hour_to`, `number_of_hours`) rather than `write_date`.
- **Odoo 19 `convert_file(..., kind=...)` deprecation:** Passing `kind='views'` or `kind='data'` emits `DeprecationWarning: The kind argument is deprecated in Odoo 19`. Call `convert_file(env, module, filename, {}, mode='update')` directly.

## Verification

```bash
/Users/gamal/.pyenv/versions/3.11.9/bin/python3 /Users/gamal/odoo/odoo19.0/odoo-bin \
  -c /Users/gamal/odoo/odoo19.0/solargy.conf \
  -d solargy_test_clone \
  --data-dir=/tmp/solargy_test_clone_data \
  -u solargy_hr \
  --test-enable \
  --test-tags /solargy_hr \
  --stop-after-init
```

## References

- Related file: `performance/batch-absence-detection-across-working-calendars.md`
- Related file: `orm/hr-payroll-odoo19-egypt-basic-fixed-wage-unpaid-double-deduction-and-calendar-out.md`
