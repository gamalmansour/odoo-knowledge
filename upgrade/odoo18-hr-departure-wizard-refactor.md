# hr.departure.wizard Refactor & Mandatory departure_reason_id in Odoo 18

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `upgrade`, `migration`, `hr`, `hr.departure.wizard`, `departure_reason_id`, `resignation`, `not-null`, `ValueError`

---

## Problem

When triggering automated employee departure or resignation approval workflows ported from Odoo ≤ 17 into Odoo 18, two cascading crashes occur:

### Crash 1: Invalid Field on Wizard Creation
```python
ValueError: Invalid field 'archive_private_address' on model 'hr.departure.wizard'
```
or
```python
ValueError: Invalid field 'archive_allocation' on model 'hr.departure.wizard'
```

### Crash 2: Mandatory Departure Reason Not Null Constraint
```
psycopg2.errors.NotNullViolation: null value in column "departure_reason_id" of relation "hr_departure_wizard" violates not-null constraint
```

---

## Root Cause

1. **Wizard Fields Cleaned Up in Odoo 18:**
   In Odoo 17 and earlier, `hr.departure.wizard` defined boolean flags such as `archive_private_address`, `archive_allocation`, and `cancel_leaves`. In Odoo 18, the departure wizard was refactored, dropping legacy fields in favor of direct state handlers. Passing these removed fields in `create()` raises an immediate `ValueError: Invalid field`.

2. **Mandatory `departure_reason_id`:**
   In Odoo 18, `departure_reason_id = fields.Many2one('hr.departure.reason', required=True)` is enforced at both the ORM level and the database schema level (`NOT NULL`). If custom resignation or offboarding code creates `hr.departure.wizard` without explicitly passing a `departure_reason_id`, the SQL transaction fails immediately.

---

## Solution ✅

When creating `hr.departure.wizard` programmatically from custom resignation, termination, or offboarding models:

1. **Resolve or Fallback `departure_reason_id`:**
   Ensure a valid `departure_reason_id` is supplied. If not selected by the user on the custom document, query the default reason from `hr.departure.reason`.

2. **Dynamic Wizard Field Introspection:**
   Only pass boolean action flags if they actually exist on `self.env['hr.departure.wizard']._fields`.

```python
# Safe Odoo 18 departure wizard invocation
def action_confirm_resignation(self) -> None:
    for rec in self:
        # 1. Fallback departure reason
        reason_id = rec.departure_reason_id.id if hasattr(rec, 'departure_reason_id') and rec.departure_reason_id else False
        if not reason_id:
            default_reason = self.env['hr.departure.reason'].search([], limit=1)
            reason_id = default_reason.id if default_reason else False

        wizard_vals = {
            'employee_id': rec.employee_id.id,
            'departure_reason_id': reason_id,
            'departure_description': rec.reason or 'Resignation',
            'departure_date': rec.expected_revealing_date or fields.Date.today(),
        }

        # 2. Inspect available fields dynamically across versions
        wizard_fields = self.env['hr.departure.wizard']._fields
        if 'archive_allocation' in wizard_fields:
            wizard_vals['archive_allocation'] = True
        if 'archive_private_address' in wizard_fields:
            wizard_vals['archive_private_address'] = True
        if 'cancel_leaves' in wizard_fields:
            wizard_vals['cancel_leaves'] = True

        # 3. Create and execute
        wizard = self.env['hr.departure.wizard'].create(wizard_vals)
        wizard.action_register_departure()
```

---

## ⚠️ Pitfalls

- **Hardcoded Reason IDs:** Never hardcode `departure_reason_id = 1`. In migrated databases or multi-company setups, IDs differ. Always search with domain or use a configured XML ID fallback.
- **Wizard Confirmation Context:** In Odoo 18, `action_register_departure()` changes the employee status (`active=False` or `departure_date`). Ensure downstream logic that references the employee does not fail due to record archiving (e.g. searching with `active_test=False` if looking up departed employees).

---

## Verification

Run an automated test confirming that resignation/departure creates the wizard and archives the employee without database exceptions:

```python
wizard = self.env['hr.departure.wizard'].create({
    'employee_id': self.test_employee.id,
    'departure_reason_id': self.env['hr.departure.reason'].search([], limit=1).id,
})
wizard.action_register_departure()
self.assertFalse(self.test_employee.active)
```
