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

### 3. Model Access Rights (`ir.model.access.csv`)
Grant `read` and `write` access to `base.group_portal` for the HR models you wish to expose.

### 4. Portal Controllers
Create a custom portal controller inheriting `CustomerPortal` from `odoo.addons.portal.controllers.portal`. Ensure all data fetched uses the standard ORM, which will automatically respect the strict record rules we defined.

```python
employee = request.env['hr.employee'].search([('user_id', '=', request.env.user.id)], limit=1)
```

## Pitfalls (Pre-mortem)
- **IDOR Vulnerability:** Do NOT use `.sudo()` blindly in portal controllers to fetch HR data based on URL IDs (e.g., `/my/leave/15`). A user could change the ID to view another employee's request. Always rely on ORM record rules without `.sudo()`.
- **Menu Caching:** Sometimes Portal Menus don't update if `website` is installed due to caching. Ensure `t-cache` isn't blocking dynamic HR counters.

## Versions
Verified on Odoo 17, 18, 19.
