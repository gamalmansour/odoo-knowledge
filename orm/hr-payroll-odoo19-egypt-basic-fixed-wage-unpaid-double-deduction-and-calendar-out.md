# Odoo 19 Egyptian Payroll: Fixed `BASIC` Wage, `LEAVE90`/`OUT` Double-Deduction & 110% PDF Inflation Trap, and 30-Day Calendar `OUT` Days

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr_payroll`, `l10n_eg_hr_payroll`, `hr.payslip`, `hr.payslip.worked_days`, `BASIC`, `paid_amount`, `EGLEAVE90`, `LEAVE90`, `OUT`, `30-day-month`, `odoo19`

---

## Problem

> In Odoo 19 Enterprise Payroll with `l10n_eg_hr_payroll` (*Egypt: Regular Pay*), four coupled defects distort payslips whenever an employee takes Unpaid Leave (`LEAVE90`), resigns/joins mid-period (`OUT`), or has multi-line worked days:
> 1. **Double-Deduction & `BASIC` Mutation:** Core `BASIC` uses `result = payslip.paid_amount`. Whenever `LEAVE90` has `is_paid = False` or `OUT` exists without rule-aware `attendance_hours`, `paid_amount` drops below `version.wage` (reducing `BASIC`) **and** `EGLEAVE90` / `OUT` deducts the days a second time! Even on 100% paid multi-line months (e.g. `1d LEAVE120 + 2d LEAVE105 + 19d WORK100`), per-line 2-decimal rounding makes `paid_amount = 8,400.01` instead of `8,400.00`.
> 2. **110% PDF `Earnings` Inflation Trap:** If a developer naively hardcodes `wd.code not in ('OUT', 'LEAVE90')` in `HrPayslipWorkedDays._compute_amount()` while `LEAVE90` is **not** listed in `struct_id.unpaid_work_entry_type_ids` (`LEAVE90.is_paid == True`, the default on `Egypt: Regular Pay`), `WORK100.amount` becomes `100%` of `wage` **plus** `LEAVE90.amount` (`~10%`), inflating `paid_amount` and the Payslip PDF `Earnings` table above `100%` of contract wage!
> 3. **Workday vs Calendar-Day `OUT` Under-Deduction & `UnboundLocalError`:** Standard `reference_calendar.get_work_duration_data()` counts only Sun–Thu working days for `OUT` (e.g. `9.0` workdays instead of `11.0` calendar days on `Oct 12–22`, skipping Friday/Saturday `Oct 16–17`), even though `OUT` divides `(BASIC + BASICALW) / 30` per calendar day. Worse, if `uncovered_dates` is only initialized inside `else:` of `if not covered_ranges:`, a 100% out-of-contract slip crashes with `UnboundLocalError: cannot access local variable 'uncovered_dates'`.
> 4. **Inline Worked-Days Overrides Wiped on Upgrade:** Editing `worked_days_line_ids.number_of_days = 0` inline on a draft payslip in Odoo 19 does **not** set `payslip.edited = True`, so a `post_init` hook calling `draft_slips._compute_worked_days_line_ids()` wipes HR's manual overrides.

```
UnboundLocalError: cannot access local variable 'uncovered_dates' where it is not associated with a value
```

## Root Cause

1. `l10n_eg_hr_payroll` ships both `BASIC = payslip.paid_amount` and separate `DED` rules (`EGLEAVE90`, `OUT`, `EGSICKLEAVE0`) that deduct `(BASIC + BASICALW) / 30 * days`, mixing core prorated-earnings architecture with 30-day subtractive-deduction architecture.
2. `HrPayslipWorkedDays._compute_amount()` in `enterprise/hr_payroll/models/hr_payslip_worked_days.py` includes all non-extra `worked_days_line_ids` in `attendance_hours`, and its `@api.depends` omits `payslip_id.struct_id.unpaid_work_entry_type_ids` and sibling `payslip_id.worked_days_line_ids.is_paid` (since `sum_worked_hours` does not change value when `is_paid` flips).
3. `hr.payroll.edit.payslip.lines.wizard` sets `payslip.edited = True`, whereas inline edits on `worked_days_line_ids` leave `payslip.edited = False`.

## Solution ✅

1. **Fix `BASIC` on Egyptian structures (`country_id.code == 'EG'`) to `version.wage` for monthly contracts while keeping `payslip.paid_amount` for hourly contracts:**

```python
eg_basic_rules = self.env['hr.salary.rule'].sudo().search([
    ('code', '=', 'BASIC'),
    ('struct_id.country_id.code', '=', 'EG'),
    ('active', '=', True),
])
if eg_basic_rules:
    eg_basic_rules.write({
        'amount_select': 'code',
        'amount_python_compute': (
            "result = payslip.paid_amount if payslip.wage_type == 'hourly' else version.wage"
        ),
    })
```

2. **Make `HrPayslipWorkedDays._compute_amount()` exclude a line from `attendance_hours` ONLY when `(wd.code == 'OUT' and has_out_rule)` OR `(not wd.is_paid and matching_unpaid_rule_is_active)`, and declare complete `@api.depends`:**

```python
class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.depends('payslip_id.struct_id.unpaid_work_entry_type_ids')
    def _compute_is_paid(self) -> None:
        super()._compute_is_paid()

    @api.depends(
        'is_paid', 'number_of_hours', 'payslip_id', 'version_id.wage', 'version_id.hourly_wage',
        'payslip_id.sum_worked_hours', 'payslip_id.worked_days_line_ids.is_paid',
        'payslip_id.worked_days_line_ids.number_of_hours', 'payslip_id.struct_id.rule_ids.active',
        'payslip_id.struct_id.rule_ids.code', 'work_entry_type_id.amount_rate',
        'work_entry_type_id.is_extra_hours',
    )
    def _compute_amount(self) -> None:
        super()._compute_amount()
        for worked_days in self:
            slip = worked_days.payslip_id
            if (
                not slip or slip.edited or slip.state != 'draft'
                or not worked_days.version_id or worked_days.code == 'OUT'
                or not worked_days.is_paid or slip.wage_type == 'hourly'
            ):
                continue
            active_codes = {r.code for r in slip.struct_id.rule_ids if r.active} if slip.struct_id else set()
            has_out_rule = 'OUT' in active_codes
            has_unpaid_rule = 'EGLEAVE90' in active_codes
            has_unpaid_sick_rule = 'EGSICKLEAVE0' in active_codes
            if not (has_out_rule or has_unpaid_rule or has_unpaid_sick_rule):
                continue
            attendance_hours = sum(
                wd.number_of_hours
                for wd in slip.worked_days_line_ids
                if not wd.work_entry_type_id.is_extra_hours
                and (wd.code != 'OUT' or not has_out_rule)
                and (wd.is_paid or not (has_unpaid_sick_rule if wd.code == 'EGSICKLEAVE0' else has_unpaid_rule))
            ) or 1.0
            hourly_rate = slip.version_id.contract_wage / attendance_hours
            worked_days.amount = hourly_rate * worked_days.number_of_hours * worked_days.work_entry_type_id.amount_rate
```

3. **Initialize `uncovered_dates` in all branches of `_get_worked_day_lines()`, filter `covered_ranges` to `r_start <= r_end`, and normalize `OUT` to 30 calendar days on Egyptian structures:**

```python
uncovered_dates: list[date] = []
if not covered_ranges:
    cur_d = self.date_from
    while cur_d <= self.date_to:
        uncovered_dates.append(cur_d)
        cur_d += timedelta(days=1)
...
if has_eg_out_rule and uncovered_dates:
    period_days = (self.date_to - self.date_from).days + 1
    if len(uncovered_dates) >= period_days:
        out_days = 30.0
    elif period_days == 30:
        out_days = float(len(uncovered_dates))
    else:
        out_days = round(len(uncovered_dates) * 30.0 / period_days, 4)
    hpd = (reference_calendar.hours_per_day if reference_calendar else 8.0) or 8.0
    out_hours = round(out_days * hpd, 2)
```

## ⚠️ Pitfalls

- **Never exclude `LEAVE90` by code when `LEAVE90.is_paid == True`:** In `report_payslip_templates.xml`, the PDF `Earnings` table prints all `worked_days_line_ids` with `code != 'OUT'`. Excluding `LEAVE90` from `attendance_hours` while `LEAVE90.is_paid == True` makes `WORK100.amount == 100% wage` AND `LEAVE90.amount > 0`, inflating the PDF `Earnings` total above `100%` of contract salary!
- **Never symlink a test clone's filestore (`filestore/db_clone -> filestore/db_live`):** Odoo's `ir.attachment` garbage collector runs during post-install tests and will delete production files from the shared directory!
- **Skip attendance penalty recalculation when fixing historical `resource_calendar_id` on a resigned employee's contract:** If `HrVersion.write()` hooks into `action_recalculate_attendance_policy()`, pass `with_context(solargy_skip_attendance_recalc=True)` so historical punches under an older schedule do not fabricate new `LATE_DED` penalties on open settlement payslips.
- **Unrounded `categories['DED']` accumulation:** Odoo sums unrounded rule floats inside `categories['DED']` (`-1333.3333... + -7333.3333... = -8666.6667`) before rounding `NET`, so `20,000 - 1,333.33 - 7,333.33` produces `NET = 11,333.33` (`20,000 * 17 / 30`), not `11,333.34`.

## Verification

```bash
/Users/gamal/.pyenv/versions/3.11.9/bin/python3 /Users/gamal/odoo/odoo19.0/odoo-bin \
  -c /Users/gamal/odoo/odoo19.0/solargy.conf \
  -d solargy_test_clone \
  -u solargy_hr \
  --test-enable \
  --test-tags /solargy_hr:TestPayrollUnpaidAndOutOfContract \
  --stop-after-init \
  --no-http
```

## References

- Related file: `orm/hr-payroll-odoo19-midperiod-renewal-work-entry-gaps-and-worked-leaves-singleton.md`
- Related file: `misc/payroll-30-day-month-invert-basic-not-7day-calendar.md`
- Module implementation: `solargy_hr/models/hr_payslip.py`, `solargy_hr/tests/test_payroll_unpaid_out.py`
