# Invalid field 'company_dependent' on model 'ir.sequence'

## Metadata
- **Category:** Upgrade
- **Severity:** 🔴 Critical
- **Odoo Versions:** 17, 18, 19
- **Tags:** `upgrade`, `migration`, `ir.sequence`, `company_dependent`
- **Last Verified:** 2026-06-08
- **Author:** ENG/Gamal Mansour

## Problem ❌
When migrating Odoo modules from v16 (or older) to v17+, defining an `ir.sequence` in XML using `<field name="company_dependent">True</field>` causes a fatal server crash during installation or upgrade:
```text
ValueError: Invalid field 'company_dependent' on model 'ir.sequence'
```

## Root Cause 🔍
The `company_dependent` boolean field was removed from the `ir.sequence` model in Odoo 17. Instead, Odoo 17 relies purely on the `company_id` field to determine if a sequence is company-dependent or global.

## Solution ✅
Replace the `company_dependent` definition with `company_id` set to `False` (for global) or assign a specific company ID. 
For a standard sequence that should work across companies or be managed per-company dynamically:

**Before (Odoo 16 and below):**
```xml
<record id="seq_project_work_order" model="ir.sequence">
    <field name="name">Project Work Order</field>
    <field name="code">project.work.order</field>
    <field name="prefix">WO/%(year)s/</field>
    <field name="padding">5</field>
    <field name="company_dependent">True</field>
</record>
```

**After (Odoo 17+):**
```xml
<record id="seq_project_work_order" model="ir.sequence">
    <field name="name">Project Work Order</field>
    <field name="code">project.work.order</field>
    <field name="prefix">WO/%(year)s/</field>
    <field name="padding">5</field>
    <field name="company_id" eval="False"/>
</record>
```

## ⚠️ Pitfalls
- Do NOT just delete the field if you want it to be global, as it might default to the `env.company` installing the module, causing issues for other companies in a multi-company environment. Always use `<field name="company_id" eval="False"/>` to explicitly make it global.
