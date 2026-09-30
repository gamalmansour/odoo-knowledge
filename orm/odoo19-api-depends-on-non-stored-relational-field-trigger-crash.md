# Odoo 19: @api.depends on Non-Stored Relational Field Causes Trigger Crash

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-09-30                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo-19`, `orm`, `api.depends`, `trigger-tree`, `non-stored`, `hr.attendance`, `hr.version`

---

## Problem

When overriding a computed method in an inherited model and adding `@api.depends("relational_field.field_name")` where `relational_field` is an **un-stored** computed relation (e.g. `linked_overtime_ids` on `hr.attendance`), the system issues a warning at registry build time:

```text
UserWarning: Field 'hr.attendance.linked_overtime_ids' in dependency of hr.attendance.overtime_hours should be searchable. This is necessary to determine which records to recompute when hr.attendance.overtime.line.duration is modified. You should either make the field searchable, or simplify the field dependency.
```

Later, whenever a record of the target relation (`hr.attendance.overtime.line`) is created or modified, Odoo's trigger tree attempts to search for the parent records using the non-stored field:

```text
records = model.search([(field.name, 'in', real_records.ids)], order='id')
  File "odoo/orm/fields_relational.py", line 783, in condition_to_sql
    raise ValueError(f"Cannot convert {self} to SQL because it is not stored")
ValueError: Cannot convert hr.attendance.linked_overtime_ids to SQL because it is not stored
```

## Root Cause

1. In Odoo 19, the ORM constructs an inverse trigger dependency graph (`pool.get_trigger_tree()`).
2. When field `A` depends on `B.subfield`, modifying `subfield` on `B` triggers a reverse search on `A` with domain `[('B', 'in', record_ids)]`.
3. If relational field `B` is a computed field without `store=True` (and lacks a custom `search='_search_B'` method), the ORM domain cannot be converted into an SQL `WHERE` clause.
4. Core Odoo often circumvents this by NOT including the non-stored relation in `@api.depends`. For example, in `addons/hr_attendance`, both `_compute_overtime_hours` and `_compute_validated_overtime_hours` depend strictly on:
   ```python
   @api.depends('check_in', 'check_out', 'employee_id')
   ```

## Solution ✅

When inheriting and overriding such compute methods, **never** expand `@api.depends` to traverse un-stored relations. Retain core Odoo's original dependencies:

**Wrong ❌:**
```python
class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # linked_overtime_ids is NOT stored!
    @api.depends("linked_overtime_ids.duration")
    def _compute_overtime_hours(self):
        super()._compute_overtime_hours()
        ...
```

**Correct ✅:**
```python
class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Match core Odoo's exact dependencies on stored fields
    @api.depends('check_in', 'check_out', 'employee_id')
    def _compute_overtime_hours(self):
        super()._compute_overtime_hours()
        ...
```

### Odoo 19 Contract Architecture (`hr.version`) Note:
In Odoo 19, `hr.contract` was refactored into `hr.version`.
- When an employee (`hr.employee`) is created, an initial `hr.version` is automatically instantiated with `date_version = fields.Date.today()`.
- To toggle contract-level settings (such as overtime eligibility or lateness penalty toggles), write to the related fields on `emp` directly (`emp.write({'enable_overtime': False})`) or via `emp.current_version_id.write(...)`.

## ⚠️ Pitfalls

- Never assume a relational field in core Odoo is stored. Check the core definition (`store=True` or compute without store).
- Do not add `@api.depends` on reverse relations unless the relation has a database column (`store=True`) or explicit search implementation.
- In tests, creating an `hr.version` with an older `date_version` (e.g. `2026-01-01`) than today will NOT override the employee's `current_version_id`, because `_compute_current_version_id` selects the most recent version `<= today`.

## Verification

Run test suite with:
```bash
python3 odoo-bin -c solargy.conf -d solargy --test-enable --test-tags=/solargy_hr:TestAttendancePolicy --stop-after-init
```
Verify 0 errors, 0 failures, and no `UserWarning: Field '...' in dependency of '...' should be searchable`.
