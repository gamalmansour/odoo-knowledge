# Odoo: Custom Fields on hr.employee Trigger Public Profile AccessError If Missing groups

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 13, 14, 15, 16, 17, 18, 19                 |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-09-30                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr`, `hr.employee`, `hr.employee.public`, `access-error`, `time-off`, `search_fetch`, `security`

---

## Problem

When a standard employee (non-HR user holding only `base.group_user`) performs any common operation involving employees — such as requesting Time Off (`hr.leave`), requesting an attendance permission, submitting expenses, or opening chat/activities — the action crashes with an AccessError dialog:

```text
Access Error
The fields '<custom_field>', which you are trying to read, are not available for employee public profiles.
```

Example:
```text
The fields 'biometric_id', which you are trying to read, are not available for employee public profiles.
```

## Root Cause

1. In Odoo, regular employees do NOT have direct read access to `hr.employee` (which contains private PII, contracts, bank accounts, and addresses).
2. Instead, Odoo delegates regular employee read operations to `hr.employee.public`.
3. In `hr.employee.search_fetch()` and `hr.employee.fetch()`:
   ```python
   if not self.browse().has_access('read'):
       if field_names is None:
           field_names = [field.name for field in self._determine_fields_to_fetch()]
       field_names = [f_name for f_name in field_names if f_name != 'current_version_id']
       self._check_private_fields(field_names)
   ```
4. `self._determine_fields_to_fetch()` retrieves all fields on `hr.employee` that have `prefetch=True` AND are accessible to the current user according to field-level groups (`self._has_field_access(field, 'read')`).
5. Then, `_check_private_fields(field_names)` enforces:
   ```python
   public_fields = self.env['hr.employee.public']._fields
   private_fields = [fname for fname in field_names if fname not in public_fields]
   if private_fields:
       raise AccessError(_('The fields “%s”, which you are trying to read, are not available for employee public profiles.', ','.join(private_fields)))
   ```
6. If a custom module adds ANY stored field to `hr.employee` **without** specifying `groups="hr.group_hr_user"`, Odoo considers it accessible to ordinary users. Because it does not exist on `hr.employee.public`, `_check_private_fields` immediately raises an `AccessError` blocking the user.

## Solution ✅

### Option A: Private / Administrative Fields (Recommended for HR data)
If the field is private or administrative (e.g. `biometric_id`, internal contract toggles, allowance settings, employee PINs):
Add `groups='hr.group_hr_user'` to the Python field definition and any XML view occurrences.

**Wrong ❌:**
```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    biometric_id = fields.Char(string='Biometric ID / PIN')
```

**Correct ✅:**
```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    biometric_id = fields.Char(
        string='Biometric ID / PIN',
        groups='hr.group_hr_user',
    )
```

And in XML views (search views, form views):
```xml
<field name="biometric_id" groups="hr.group_hr_user"/>
```

With `groups='hr.group_hr_user'`, `_has_field_access(field, 'read')` returns `False` for regular employees, so Odoo's prefetcher excludes it from `field_names` and `_check_private_fields` passes smoothly.

### Option B: Publicly Visible Employee Attributes
If the custom field is genuinely meant to be visible to all employees (e.g. public desk location, nickname):
Inherit and declare the field on `hr.employee.public` as well:
```python
class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    public_nickname = fields.Char(readonly=True)
```

## ⚠️ Pitfalls

- Never add a stored field to `hr.employee` without deciding whether it belongs to `hr.group_hr_user` or `hr.employee.public`.
- Non-stored computed fields typically have `prefetch=False` and avoid this, but stored fields (and stored related fields) will always be prefetched unless gated with `groups`.
- Check related fields carefully: if `related='current_version_id.some_field'` is stored on `hr.employee`, it will trigger this error unless `groups='hr.group_hr_user'` is set.

## Verification

In `odoo shell`:
```python
user = env['res.users'].search([('login', '!=', 'admin')], limit=1)
emp = user.employee_id
emp.with_user(user).search_fetch([('id', '=', emp.id)])
```
Must return the recordset without raising `AccessError: The fields '...' are not available for employee public profiles`.
