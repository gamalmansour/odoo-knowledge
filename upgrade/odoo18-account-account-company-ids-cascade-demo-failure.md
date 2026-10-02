# Odoo 18: account.account company_ids Field Change Causes Silent Cascading Demo Data Failure

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade / orm / setup                      |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-16                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo18`, `account.account`, `company_ids`, `company_id`, `demo-data`, `graph`, `cascade-failure`, `loading`

---

## Problem

When installing or upgrading a module suite in Odoo 18 with demo data, entire downstream models (like `tender.boq.breakdown`, `project.work.order`, etc.) end up completely empty with **zero demo records**, even though demo XML files are present in the manifests and no fatal error stopped the installation.

In the database table `ir_demo_failure`:
```
ValueError: Invalid field 'company_id' on model 'account.account'
odoo.tools.convert.ParseError: while parsing .../demo_accounts.xml:5
<record id="acc_wip" model="account.account">
    ...
    <field name="company_id" ref="base.main_company"/>
</record>
```

## Root Cause

1. **Odoo 18 ORM Schema Change:** In Odoo 18, `account.account.company_id` (Many2one) was replaced by `account.account.company_ids` (Many2many) to support multi-company account sharing. Any XML demo file setting `<field name="company_id" ref="..."/>` raises `ValueError: Invalid field 'company_id' on model 'account.account'`.
2. **Silent Failure Handling in `load_demo`:** In `odoo/modules/loading.py`, when demo data fails to parse, Odoo catches the exception, creates an entry in `ir.demo_failure`, logs a warning, and sets `package.dbdemo = False` (`UPDATE ir_module_module SET demo=False`).
3. **Graph-Level Cascade Block:** In `odoo/modules/graph.py`:
   ```python
   def should_have_demo(self):
       return (hasattr(self, 'demo') or (self.dbdemo and self.state != 'installed')) and all(p.dbdemo for p in self.parents)
   ```
   If an upstream module (e.g. `construction_contract`) fails its demo load (`dbdemo = False`), **ALL downstream dependent modules** (`construction_project` -> `construction_costcode` -> `construction_rate_buildup`) evaluate `all(p.dbdemo for p in self.parents)` to `False`. As a result, Odoo silently skips loading demo data for the entire dependency tree without logging any error for the child modules!

## Solution ✅

### 1. Fix `account.account` XML declarations for Odoo 18+
Replace `company_id` with `company_ids`:
```xml
<!-- ❌ Pre-v18 syntax -->
<field name="company_id" ref="base.main_company"/>

<!-- ✅ Odoo 18+ syntax (universal tuple syntax) -->
<field name="company_ids" eval="[(4, ref('base.main_company'))]"/>
<!-- OR -->
<field name="company_ids" eval="[Command.link(ref('base.main_company'))]"/>
```

### 2. Reload Demo Data for Affected Modules
If the database was already initialized without demo data, load the demo files via python or force demo reload:
```python
from odoo.tools.convert import convert_file
convert_file(env, 'module_name', 'demo/demo_file.xml', {}, 'init', False, 'demo')
env.cr.commit()
```
And ensure `UPDATE ir_module_module SET demo = True WHERE name = 'module_name';` is set so subsequent child modules can load.

## ⚠️ Pitfalls

- **Red Herring:** Because child modules fail silently without an exception in the logs, developers spend hours debugging views, action domains, or permissions wondering why views like `tender.boq.breakdown` are empty.
- Always check `SELECT * FROM ir_demo_failure;` first whenever demo data is missing in an installed database!

## Verification

```sql
SELECT m.name, m.demo, count(b.id) 
FROM ir_module_module m 
LEFT JOIN tender_boq_breakdown b ON true 
WHERE m.name = 'construction_rate_buildup' 
GROUP BY m.name, m.demo;
```

## References

- Odoo 18 Accounting Multi-Company Account Changes
- Related file: `setup/client-demo-database-build-order-odoo18.md`
