# Odoo 19 Payroll: Mid-Period Contract Renewal False `OUT` Days, Calendar Gap Errors, and `worked_leaves` Singleton Crash

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-09                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr_payroll`, `hr_work_entry`, `hr.version`, `l10n_eg_hr_payroll`, `out-of-contract`

---

## Problem

Three cascading failures hit Odoo 19 Enterprise Payroll (`hr_payroll` + `hr_work_entry` + `l10n_eg_hr_payroll`) in real production payroll runs:

1. **False `Out of Contract` (`OUT`) & Double-Deduction on Mid-Period Contract Renewals:**
   When an employee renews their contract mid-payslip period (e.g., old `hr.version` ends `2026-09-30` and new `hr.version` starts `2026-10-01` in a `2026-09-23 -> 2026-10-22` cycle), `hr.payslip` binds to a single `version_id` and marks the days covered by the sibling version as `Out of Contract` (`OUT`). Worse, when the salary structure has an active `OUT` deduction rule (like `l10n_eg_hr_payroll`) AND `OUT` is in `worked_days_line_ids`, `HrPayslipWorkedDays._compute_amount()` prorates `BASIC` down while the `OUT` rule deducts the days a second time!
2. **"Bermuda Triangle" Calendar Gap UserError (`_check_undefined_slots`):**
   ```
   Watch out for gaps in <Employee>'s calendar
   Please complete the missing work entries of <Employee>:
    - 2026-10-11 09:00:00+03:00 -> 2026-10-11 17:00:00+03:00
   ```
3. **Singleton Crash When Regenerating Work Entries With Overlapping `time_type = 'other'` Leaves (Missions/Excuses):**
   ```
   ValueError: Expected singleton: resource.calendar.leaves(4032, 4836, 69)
   ```

## Root Cause

1. **Single-version scope on `hr.payslip`:** Core `_get_worked_day_lines_values` and `_get_worked_day_lines` only inspect `self.version_id` rather than all `employee_id.version_ids` overlapping `[date_from, date_to]`. In addition, editing `contract_date_start` on a newly created `hr.version` in Odoo 19 can overwrite the previous version's `contract_date_start` if not isolated, leaving `v_old.date_version < v_old.contract_date_start`.
2. **Unlinked `work_entry_type_id` on `hr.leave.type`:** Any approved leave whose `hr.leave.type` has `work_entry_type_id = False` (common on custom leave types like `Compensatory Days` or `Excuses`) generates `hr.work.entry` rows with `work_entry_type_id = False`, `state = 'conflict'`, `active = False`, leaving uncovered slots that fail `_check_undefined_slots`.
3. **Unsplit `worked_leaves` intervals in `addons/hr_work_entry/models/hr_version.py`:** While regular `leaves` are split into single-record intervals before calling `_get_interval_leave_work_entry_type`, `worked_leaves` (`time_type == 'other'`) are merged via `Intervals` where `interval[2]` becomes a multi-recordset `resource.calendar.leaves(...)`. `hr_work_entry_holidays` then accesses `interval[2].date_from` and crashes with `ValueError: Expected singleton`.

## Solution ✅

1. **Flatten multi-record `resource.calendar.leaves` intervals in `hr.version` before calling `super()`:**
```python
class HrVersion(models.Model):
    _inherit = 'hr.version'

    @staticmethod
    def _flatten_leave_intervals(interval):
        start, stop, leaves = interval
        if hasattr(leaves, '_name') and len(leaves) > 1:
            leaves = leaves.sorted(lambda l: (0 if l.holiday_id else 1, l.id))[:1]
            return (start, stop, leaves)
        return interval

    def _get_interval_leave_work_entry_type(self, interval, leaves, bypassing_codes):
        return super()._get_interval_leave_work_entry_type(
            self._flatten_leave_intervals(interval), leaves, bypassing_codes
        )

    def _get_more_vals_leave_interval(self, interval, leaves):
        return super()._get_more_vals_leave_interval(
            self._flatten_leave_intervals(interval), leaves
        )
```

2. **Aggregate worked hours across all overlapping `hr.version` records on `hr.payslip` and compute `OUT` only for uncovered dates:**
   - Override `_compute_worked_days_line_ids` to heal missing `work_entry_type_id` on `hr.leave.type` / `resource.calendar.leaves` and generate work entries across all overlapping versions.
   - Override `_get_worked_day_lines_values` to call `overlapping_versions.get_work_hours(self.date_from, self.date_to, domain=domain)`.
   - Override `_get_worked_day_lines` to emit `OUT` only for dates in `[self.date_from, self.date_to]` not covered by any overlapping contract version.
   - Override `HrPayslipWorkedDays._compute_amount` to exclude `OUT` hours from `attendance_hours` when the salary structure already has an active `OUT` deduction rule, preventing double deduction.

## ⚠️ Pitfalls

- **Policy flags across versions:** In Odoo 19, policy booleans on `hr.version` (such as `enable_overtime` or `enable_late_in_penalty`) must be synced across sibling `version_ids` when toggled on the Employee form (`current_version_id`), otherwise an older version in the first half of the payroll cycle will keep applying outdated flags.
- **`payslip.edited = True` freezes `worked_days.amount`:** Manually deleting a line in `worked_days_line_ids` sets `payslip.edited = True`, which causes core `_compute_amount` to skip recomputing the remaining lines' `amount`. Always heal at the `Time Off` / `Work Entries` source and use `Refresh from Work Entries`, or zero `number_of_days` without deleting paid lines.

## Verification

```bash
# Upgrade custom HR module and verify zero singleton crashes or calendar gaps
/Users/gamal/odoo/odoo19.0/.venv/bin/python3 /Users/gamal/odoo/odoo19.0/odoo-bin \
  -c /Users/gamal/odoo/odoo19.0/solargy.conf -d solargy -u solargy_hr --stop-after-init --no-http
```

## References

- Module implementation: `solargy_hr/models/hr_version.py`, `solargy_hr/models/hr_payslip.py`, `solargy_hr/models/hr_employee.py`
