# Odoo 19: hr.version Architecture, Contract Lifecycle & Payroll Integration

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 19.0                                       |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-10-06                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo19`, `payroll`, `hr.version`, `hr.contract`, `payslip`, `attendance`, `penalties`

---

## Problem

When upgrading to or developing custom HR and Payroll modules in Odoo 19:
1. `hr.contract` model is completely removed and replaced by `hr.version` (`hr_version` table).
2. Attempting to create an `hr.version` for an employee directly in test suites or programmatic code often triggers a database constraint error:
```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "hr_version_check_unique_date_version"
DETAIL: Key (employee_id, date_version)=(xxx, YYYY-MM-DD) already exists.
```
3. When validating payslips via `payslip.action_payslip_done()`, the system raises a blocking validation error:
```
odoo.exceptions.ValidationError: • No running contract over payslip period
```
4. Custom penalties and overtime hours linked to payroll are susceptible to duplicate deductions or orphan states if payslips are reset to draft or cancelled.

## Root Cause

1. **Auto-Generated Initial Version:** In Odoo 19, creating an `hr.employee` automatically generates an initial `hr.version` record with `date_version = fields.Date.today()` and `wage = 0.0`.
2. **Date Version Uniqueness:** The table has a database constraint `hr_version_check_unique_date_version` enforcing `UNIQUE(employee_id, date_version)`. Calling `env['hr.version'].create({'employee_id': emp.id, ...})` without specifying a different date causes a collision with the initial version.
3. **Contract Running Check:** `hr.payslip._filter_not_in_contract_payslips()` requires `version_id.contract_date_start` to be set and valid (`contract_date_start <= payslip.date_to` and `contract_date_end >= payslip.date_from` if defined). Setting only `date_version` does not satisfy the contract running check.
4. **State Lifecycle Locking:** Payslip inputs must participate in a strict bidirectional state machine with source disciplinary/penalty models to prevent double deductions across pay runs.

## Solution ✅

### 1. Configure the Auto-Generated Version Instead of Creating a Duplicate

In unit tests and setup scripts, write directly to the employee's existing `version_id`:

```python
# In Odoo 19, employee automatically has version_id created upon employee creation
employee.version_id.write({
    'name': 'Active Employment Contract',
    'wage': 30000.0,
    'contract_date_start': date(2026, 1, 1),
    'structure_type_id': structure.type_id.id,
    'company_id': company.id,
    'enable_overtime': True,
})
```

### 2. Defensive Wage Resolution for Deductions & Overtime

In penalty models or attendance computations, resolve wages defensively across `rec.payslip_id.version_id`, `employee.version_id`, and `employee.current_version_id`:

```python
@api.depends('employee_id', 'employee_id.version_id.wage', 'employee_id.current_version_id.wage', 'deduction_days')
def _compute_deduction_amount(self) -> None:
    for rec in self:
        wage = 0.0
        version = rec.payslip_id.version_id if rec.payslip_id and rec.payslip_id.version_id else False
        if not version and rec.employee_id:
            version = rec.employee_id.version_id or rec.employee_id.current_version_id
        if not version and 'hr.version' in self.env and rec.employee_id:
            version = self.env['hr.version'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('wage', '>', 0),
            ], limit=1)
        if version and hasattr(version, 'wage') and version.wage:
            wage = version.wage / 30.0
        rec.daily_wage = round(wage, 2)
        rec.deduction_amount = round(rec.deduction_days * rec.daily_wage, 2)
```

### 3. Bidirectional Payslip Lifecycle Hooks

Override payslip lifecycle methods in `hr.payslip` to lock penalties on confirmation and release them on cancellation:

```python
def action_payslip_done(self):
    res = super().action_payslip_done()
    for slip in self:
        confirmed_penalties = slip.attendance_penalty_ids.filtered(lambda p: p.state == 'confirmed')
        if confirmed_penalties:
            confirmed_penalties.write({'state': 'applied'})
    return res

def action_payslip_cancel(self):
    for slip in self:
        applied_penalties = slip.attendance_penalty_ids.filtered(lambda p: p.state == 'applied')
        if applied_penalties:
            applied_penalties.write({
                'state': 'confirmed',
                'payslip_id': False,
            })
    return super().action_payslip_cancel()
```

## ⚠️ Pitfalls

- **Do NOT pass `'state': 'open'` to `hr.version`:** Unlike `hr.contract` in Odoo 18 and earlier, `hr.version` in Odoo 19 does not have a `state` field. Passing `state` raises `ValueError: Invalid field 'state' in 'hr.version'`.
- **Always specify `contract_date_start`:** Omitting `contract_date_start` leaves the employee considered "out of contract" during payslip validation.
- **Hourly rate calculation:** Ensure the calendar's `hours_per_day` is used (fallback to 8.0) when calculating overtime rate: `hourly_rate = (wage / 30.0 / hours_per_day)`. Standard Egyptian labor law overtime is evaluated at `1.5 * hourly_rate`.

## Verification

Run test suite under Odoo 19:
```bash
python3 odoo-bin -c solargy.conf -d solargy -u solargy_hr --test-tags=solargy_hr.TestAttendancePolicy --stop-after-init
```
Expected output:
```
Ran 27 tests ... OK (0 failed, 0 errors)
```

## References

- Odoo 19 Core Models: `addons/hr/models/hr_version.py`, `enterprise/hr_payroll/models/hr_payslip.py`
- Solargy Implementation: `solargy_hr/models/hr_payslip.py`, `solargy_hr/models/hr_attendance_penalty.py`
