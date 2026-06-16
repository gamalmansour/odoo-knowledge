# HR Employee address_home_id Deprecation

**Category:** Upgrade  
**Tags:** upgrade, migration, hr.employee, address_home_id, work_contact_id, accounting, expenses  
**Odoo Versions:** 17, 18, 19  
**Last Verified:** 2026-06-16

## Problem
When migrating HR modules, demo data, or scripts from Odoo 16 or below to Odoo 17+, you will encounter a `ValueError: Invalid field 'address_home_id' on model 'hr.employee'` when trying to link an employee to their private `res.partner` address.

In older versions, `address_home_id` was the `Many2one` field used to link an employee to their private address partner, which was crucial for posting journals, expenses, and custody logic.

## Solution ✅
In Odoo 17, `address_home_id` was completely removed from the `hr` module. The private address fields are now individual fields directly on `hr.employee` (e.g., `private_street`, `private_city`).

However, for the purpose of linking an employee to a `res.partner` for accounting, expenses, and custody, the field was replaced by **`work_contact_id`**.

**Migration Action:**
Change all references from `address_home_id` to `work_contact_id` when accessing the employee's `res.partner` ID for financial transactions.

```xml
<!-- Odoo 16 and below -->
<field name="address_home_id" ref="partner_emp_pm_1"/>

<!-- Odoo 17+ -->
<field name="work_contact_id" ref="partner_emp_pm_1"/>
```

## ⚠️ Pitfalls
- Do NOT confuse `work_contact_id` with `address_id`. `address_id` is the **Work Address** (the company/branch location), while `work_contact_id` is the `res.partner` contact representing the employee themselves for accounting purposes.
