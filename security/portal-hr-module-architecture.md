# Exposing Internal HR Models to Portal Users

## Problem
Internal HR models (like `hr.employee`, `hr.leave`, `hr.payslip`) are designed for internal users (`base.group_user`). Sometimes, companies want to expose self-service HR functionalities (Time Off requests, Payslips, Attendance, Loans) to external/portal users (`base.group_portal`) without assigning them paid internal licenses. 

By default, portal users cannot access `hr.employee` and other HR models securely.

## Solution

### 1. Linking Portal User to Employee
Odoo `hr.employee` already has a `user_id` field. We link the `res.users` (Portal User) to the `hr.employee`. 

### 2. Record Rules
We must define strict record rules to ensure a portal user can only read/write their **own** employee record and related documents.
```xml
<record id="hr_employee_portal_rule" model="ir.rule">
    <field name="name">Employee Portal: Read/Write own record</field>
    <field name="model_id" ref="hr.model_hr_employee"/>
    <field name="domain_force">[('user_id', '=', user.id)]</field>
    <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
    <field name="perm_read" eval="1"/>
    <field name="perm_write" eval="1"/>
</record>
```

### 4. Odoo 19 Specific: `hr.version` Dependency
In Odoo 19, `hr.employee` relies heavily on `hr.version` via `_inherits`. A portal user attempting to read their `hr.employee` record will encounter a `403: Forbidden` AccessError on `version_id` unless they also have explicit access to `hr.version`.

**Fix:** Add `hr.version` to `ir.model.access.csv` for `base.group_portal` and an `ir.rule`:
```xml
<record id="hr_version_portal_rule" model="ir.rule">
    <field name="name">Employee Portal: Read/Write own version</field>
    <field name="model_id" ref="hr.model_hr_version"/>
    <field name="domain_force">[('employee_id.user_id', '=', user.id)]</field>
    <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
    <field name="perm_read" eval="1"/>
    <field name="perm_write" eval="1"/>
</record>
```

### 5. Portal Controllers
Create a custom portal controller inheriting `CustomerPortal` from `odoo.addons.portal.controllers.portal`. Ensure all data fetched uses the standard ORM, which will automatically respect the strict record rules we defined.

```python
employee = request.env['hr.employee'].search([('user_id', '=', request.env.user.id)], limit=1)
```

### 6. Keep Portal Access Read-Only (Least Privilege)
Grant `perm_write=0` on `hr.employee` / `hr.version` ACLs and rules unless the portal
actually has an edit-profile feature. With write granted, any field **not** protected by
a `groups=` attribute is writable by the portal user directly over JSON-RPC/XML-RPC —
the portal UI not exposing an edit form does not protect anything. (`wage` happens to be
`hr.group_hr_manager`-protected in Odoo 19, but don't rely on field-level groups alone.)

### 7. Rendering Related Records: sudo AFTER ownership, confined to render
The profile page reads `employee.parent_id.name` (the manager = ANOTHER `hr.employee`
the record rule hides) and `department_id` / `job_id` (no portal ACL). Fetch the
employee **without** sudo (rule proves ownership), then pass `employee.sudo()` only to
the template:

```python
employee = request.env['hr.employee'].search([('user_id', '=', request.env.user.id)], limit=1)  # rule enforces ownership
values = {'employee': employee.sudo()}  # sudo confined to rendering related fields
```
Adding read ACLs for `hr.department`/`hr.job` instead does NOT solve `parent_id` (it's
an `hr.employee` blocked by the same own-record rule) and leaks all departments/jobs
company-wide via RPC.

### 8. Filter Requestable Leave Types Like the Core Does
Do not offer `hr.leave.type.search([])` in the portal request form. Match the core domain
(`hr_leave.py`): `['|', ('requires_allocation', '=', False), ('has_valid_allocation', '=', True)]`
with `with_context(employee_id=employee.id)` (the `_search_valid` method reads the employee
from context), plus `('company_id', 'in', [False, employee.company_id.id])`.

## Pitfalls (Pre-mortem)
- **IDOR Vulnerability:** Do NOT use `.sudo()` blindly in portal controllers to fetch HR data based on URL IDs (e.g., `/my/leave/15`). A user could change the ID to view another employee's request. Always rely on ORM record rules without `.sudo()`.
- **Menu Caching:** Sometimes Portal Menus don't update if `website` is installed due to caching. Ensure `t-cache` isn't blocking dynamic HR counters.

## Versions
Verified on Odoo 17, 18, 19.
