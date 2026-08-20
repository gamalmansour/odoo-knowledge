# Multi-Module Suite Res Groups Uniqueness and Cross-Module References

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `res.groups`, `unique`, `cross-module`, `ir.model.access`, `permissions`

---

## Problem

When developing a suite of interconnected modules (e.g. `medical_hcp`, `medical_territory`, `medical_call_visit`, `medical_coaching`), duplicating group definitions (`<record id="group_..." model="res.groups">`) with identical names across multiple security XML files causes a database constraint violation on installation/upgrade:

```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "res_groups_name_uniq"
DETAIL: Key (category_id, name)=(..., Medical Representative) already exists.
```

## Root Cause

In Odoo, `res.groups` enforces a unique constraint on `(category_id, name)`. Even if XML IDs are different per module (`medical_hcp.group_mr` vs `medical_territory.group_mr`), defining records with the same `category_id` and string `name` violates Postgres table constraints upon loading.

## Solution ✅

1. **Declare Groups Only Once in the Base Module:**
   Define `module_category_*` and all role groups (`group_*`) exclusively in the foundational module (e.g., `medical_hcp/security/medical_hcp_security.xml`).

2. **Reference the Base Module XML IDs Everywhere Else:**
   In all satellite and dependent modules, reference the base module's group XML IDs in `ir.model.access.csv` and `ir.rule` definitions:

   ```csv
   # In medical_territory/security/ir.model.access.csv:
   access_territory_mr,territory.mr,model_medical_territory_territory,medical_hcp.group_medical_crm_mr,1,0,0,0
   ```

   ```xml
   <!-- In medical_territory/security/medical_territory_security.xml: -->
   <record id="medical_territory_mr_rule" model="ir.rule">
       <field name="name">Medical Rep: Own Territories</field>
       <field name="model_id" ref="model_medical_territory_territory"/>
       <field name="domain_force">[('rep_ids', 'in', [user.employee_id.id])]</field>
       <field name="groups" eval="[(4, ref('medical_hcp.group_medical_crm_mr'))]"/>
   </record>
   ```

3. **Verify Module Dependencies:**
   Ensure every satellite module lists the base security-owning module in `__manifest__.py['depends']`.

## ⚠️ Pitfalls

- Never copy-paste security group XML blocks between modules in the same project suite.
- Menu items with `groups="group_name"` must use the fully qualified XML ID `groups="base_module.group_name"` if defined outside the base module.

## Verification

```bash
odoo-bin -c odoo.conf -d test_db -i base_module,satellite_module_1,satellite_module_2 --stop-after-init
```
