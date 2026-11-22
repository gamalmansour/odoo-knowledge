# Odoo 19.0 Breaking Removals: `res.groups.users`, `tools.ustr()`, and `contract` in Salary Rules

| Field         | Value                  |
|---------------|------------------------|
| Category      | upgrade                |
| Odoo Versions | 19                     |
| Severity      | 🔴 Critical            |
| Last Verified | 2026-11-22             |
| Author        | ENG/Gamal Mansour      |

**Tags:** `odoo19`, `upgrade`, `res.groups`, `all_user_ids`, `tools.ustr`, `hr.version`, `hr_payroll`, `salary-rules`

---

## Problem

Custom modules migrated from Odoo 16/17/18 to Odoo 19.0 install cleanly without syntax errors, then crash at runtime with `AttributeError` or `NameError` in three silent places:

```text
AttributeError: 'res.groups' object has no attribute 'users'
AttributeError: module 'odoo.tools' has no attribute 'ustr'
NameError: name 'contract' is not defined  (inside hr.salary.rule amount_python_compute)
```

## Root Cause

1. **`res.groups.users` renamed:** Odoo 19 renamed the group-membership relation on `res.groups` to `user_ids` (direct) / `all_user_ids` (direct + implied). Any cron or notification helper reading `group.users` crashes on first execution.
2. **`odoo.tools.ustr()` removed:** The Python 2/3 compatibility helper `tools.ustr()` was dropped in Odoo 19. Any exception handler calling `tools.ustr(e)` crashes inside its own `except` block.
3. **`hr.contract` merged into `hr.version`:** Payroll rule Python evaluation context in Odoo 19 exposes `version` instead of `contract`. XML salary rules migrated from Odoo 18 that still evaluate `contract.wage` crash on every payslip computation (and if the XML record isn't updated via a `noupdate="1"` repair action, existing DB rules keep crashing even after code fixes).

## Solution ✅

1. **Replace `group.users` with `group.all_user_ids`:**
```python
hr_group = self.env.ref('hr.group_hr_user', raise_if_not_found=False)
hr_users = hr_group.all_user_ids.filtered('active') if hr_group else self.env['res.users']
```

2. **Replace `tools.ustr(e)` with standard `str(e)`:**
```python
except UserError as e:
    raise UserError(_("Operation failed: %s") % str(e))
```

3. **Update salary rule Python code to use `version` + ship an idempotent repair server action for existing DBs:**
```xml
<data noupdate="1">
    <record id="hr_rule_late" model="hr.salary.rule">
        <field name="amount_python_compute">
hours_per_day = version.resource_calendar_id.hours_per_day or 8.0
result = -((version.wage / (30.0 * hours_per_day)) * worked_days.LATE.number_of_hours)
        </field>
    </record>
</data>
```

## ⚠️ Pitfalls

- **`noupdate="1"` on salary rules:** Wrapping salary rules in `<data noupdate="1">` protects client customizations on future upgrades, but means existing databases that already loaded the broken `contract.wage` formula will NOT get the fix on `-u`. Always ship an idempotent `ir.actions.server` (or controlled upgrade step) to repair existing DB rows safely.
- **Hidden in `except` blocks and crons:** `tools.ustr()` and `group.users` often sit inside scheduled crons or error handlers that unit tests don't always trigger — always grep the entire custom addons tree (`grep -rn "group\.users\|tools\.ustr\|contract\.wage"`).
- **Check `ir.sequence` `noupdate="1"` at the same time:** Legacy modules frequently define `<record model="ir.sequence">` inside `<data>` without `noupdate="1"`, resetting `number_next` or prefixes on every `-u`.

## Verification

```bash
grep -rn "group\.users\|tools\.ustr\|contract\.wage" /path/to/custom_addons/
```

## References

- Related file: `upgrade/odoo19-hr-contract-merged-into-hr-version.md`
