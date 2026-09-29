# Odoo 19 Reverts hr.leave.type.requires_allocation to Boolean

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 19                                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr_holidays`, `hr.leave.type`, `requires_allocation`, `odoo19`, `tests`, `validation`

---

## Problem

When creating or modifying `hr.leave.type` records in Odoo 19 (e.g. in test fixtures or seed data) using the Odoo 17/18 convention `'requires_allocation': 'no'`, Odoo raises a `ValidationError` when employees request leaves without an existing allocation:

```
odoo.exceptions.ValidationError: You do not have any allocation for this time off type.
Please request an allocation before submitting your time off request.
```

## Root Cause

In Odoo 17 and 18, `hr.leave.type.requires_allocation` was a `fields.Selection` with values `[('yes', 'Yes'), ('no', 'No')]`.

In Odoo 19 (`addons/hr_holidays/models/hr_leave_type.py`), Odoo reverted `requires_allocation` back to a `fields.Boolean`:

```python
requires_allocation = fields.Boolean(
    default=True,
    required=True,
    string='Requires allocation'
)
```

When passing `'no'` to a Boolean field, Python evaluates non-empty strings as truthy (`bool('no') == True`). Consequently, Odoo stores `requires_allocation = True`, requiring employees to have allocations even when the code intended no allocation requirement.

## Solution ✅

Explicitly pass standard Python boolean values (`True` or `False`) instead of strings when creating or updating `hr.leave.type` in Odoo 19:

```python
# In tests or model logic:
leave_type = self.env['hr.leave.type'].create({
    'name': 'Casual Leave No Allocation',
    'requires_allocation': False,  # MUST be False, NOT 'no'
    'request_unit': 'day',
    'leave_validation_type': 'no_validation',
})
```

## ⚠️ Pitfalls

- **Truthy Strings:** In Python, any non-empty string including `'no'`, `'false'`, `'0'` evaluates to `True` when assigned or cast to a boolean field.
- **Search Domains:** Use `('requires_allocation', '=', False)` instead of `('requires_allocation', '=', 'no')` in XML domains and Python searches.

## Verification

Run test cases creating leave requests on non-allocation leave types without prior allocation:

```bash
odoo-bin -c solargy.conf -d solargy --test-enable --test-tags=/solargy_hr:TestAttendancePolicy --stop-after-init
```

All leave creation requests complete without raising allocation validation errors.

## References

- Odoo Core: `addons/hr_holidays/models/hr_leave_type.py`
- Related file: `upgrade/hr-leave-employee-ids-removed-odoo18.md`
