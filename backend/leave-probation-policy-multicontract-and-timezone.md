# Leave Probation Policy — False Positives from Contract Renewals, Migrated Data and UTC Shift

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-01                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr_holidays`, `leave_policy`, `probation`, `hr_version`, `timezone`

---

## Problem

When creating or approving an Annual or Casual leave for an existing employee who has been with the company for over a year (or has past leave allocations), Odoo unexpectedly raises a `ValidationError`:

```text
ValidationError: According to Solargy attendance policy, employees under probation (first 3 months of service) are not entitled to request Annual or Casual leaves (Current service: 9 days, required: 90 days).
```

Even though the employee is an established senior employee, the system claims their service is only 9 days.

## Root Cause

1. **Contract Renewals / Version Amendments in Odoo 19:**
   In Odoo 19, `hr.version` replaces `hr.contract`. When an employee's contract is renewed or amended, a new version is created with a new `contract_date_start` (e.g., September 21/22 of the renewal year). The related field `hr.employee.contract_date_start` points to `current_version_id.contract_date_start`, which reflects the *renewal* date, not the original hiring date!
2. **Ignoring Permanent Probation Completion:**
   Employees have a computed/stored `probation_end_date` (typically 90 days after hire date). An employee whose probation ended a year ago should never be subjected to probation-based blocks, regardless of whether a leave belongs to a past year allocation or current year.
3. **Timezone Offset on UTC `date_from`:**
   In Odoo, `hr.leave.date_from` is a `fields.Datetime` stored in UTC. In UTC+2 or UTC+3 timezones (e.g. Cairo), a leave starting at midnight on October 1st is stored as `09/30 21:00:00 UTC`. Calling `rec.date_from.date()` directly takes the UTC date (`09/30`), causing an off-by-one error in calculated service days.

## Solution ✅

Refactor the probation check in `hr.leave` constraint:

```python
# 1. Convert date_from to local timezone before extracting date
tz_name = rec.tz or rec.employee_id.tz or self.env.user.tz or 'Africa/Cairo'
try:
    user_tz = pytz.timezone(tz_name)
    leave_date = rec.date_from.astimezone(user_tz).date()
except Exception:
    leave_date = rec.date_from.date()

# 2. Check if employee already passed probation officially
is_past_probation = False
emp = rec.employee_id
if 'probation_end_date' in emp._fields and emp.probation_end_date:
    if leave_date >= emp.probation_end_date or fields.Date.today() >= emp.probation_end_date:
        is_past_probation = True

if not is_past_probation:
    # 3. Find true initial hire date across ALL versions and contracts
    all_dates = []
    if 'version_ids' in emp._fields and emp.version_ids:
        all_dates.extend([v.contract_date_start for v in emp.version_ids if v.contract_date_start])
    if 'first_contract_date' in emp._fields and emp.first_contract_date:
        all_dates.append(emp.first_contract_date)
    if 'contract_date_start' in emp._fields and emp.contract_date_start:
        all_dates.append(emp.contract_date_start)
    if 'hr.contract' in self.env:
        contracts = self.env['hr.contract'].search([
            ('employee_id', '=', emp.id),
        ], order='date_start asc')
        all_dates.extend([c.date_start for c in contracts if c.date_start])

    hire_date = min(all_dates) if all_dates else (
        emp.create_date.date() if emp.create_date else False
    )

    if hire_date:
        current_service = (fields.Date.today() - hire_date).days
        service_days = (leave_date - hire_date).days
        if current_service >= 90:
            is_past_probation = True
        elif service_days < 90:
            raise ValidationError(_(
                "According to Solargy attendance policy, employees under probation (first 3 months of service) "
                "are not entitled to request Annual or Casual leaves (Current service: %d days, required: 90 days).",
                max(0, service_days),
            ))
```

## ⚠️ Pitfalls

- Never rely on `rec.employee_id.contract_date_start` alone when checking tenure or probation in Odoo 19: always inspect `emp.version_ids` to find the earliest date.
- Never take `.date()` directly on `fields.Datetime` without timezone conversion in leave calculations.
- Always check if `current_service >= 90` or `probation_end_date <= today`: an employee with 1+ years of service is never in probation.

## Verification

Run test suite:
```bash
python3 odoo-bin -c solargy.conf -d solargy --test-enable --test-tags=/solargy_hr:TestAttendancePolicy --stop-after-init
```
