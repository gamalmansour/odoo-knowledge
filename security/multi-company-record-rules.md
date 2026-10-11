# Multi-Company Record Rules (`ir.rule`) for Custom Models

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `multi-company`, `ir.rule`, `access-rights`

---

## Problem

> Custom models in a multi-company environment leak data across companies by default. If a model has a `company_id` field but lacks a corresponding record rule (`ir.rule`), users from Company A will be able to read, write, and delete records belonging to Company B, leading to massive data breaches and data integrity issues.

## Root Cause

> Standard `ir.model.access.csv` only controls model-level CRUD permissions. Record-level permissions (restricting access to specific rows based on context or fields like `company_id`) are governed exclusively by `ir.rule`. Without an explicit rule, all records are visible to anyone with model-level access.

## Solution ✅

> 1. Ensure the custom model has a `company_id` field.
> 2. Create an `ir.rule` in a security XML file (e.g., `security/ir.rules.xml`) that restricts access based on the user's allowed companies (`company_ids`).

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="rule_my_custom_model_company" model="ir.rule">
            <field name="name">My Custom Model Multi-Company</field>
            <field name="model_id" ref="model_my_custom_model"/>
            <field name="domain_force">['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</field>
        </record>
    </data>
</odoo>
```

> 3. Add `security/ir.rules.xml` to the `data` array in `__manifest__.py`.

## ⚠️ Pitfalls

- **Missing `False` condition:** If you omit `('company_id', '=', False)`, records intended to be global (shared across all companies) will become inaccessible to everyone. Always include it unless you explicitly want to forbid global records.
- **Child Models:** If a child model (e.g., lines) doesn't have a `company_id` field, you must traverse to the parent to check the company (e.g., `('parent_id.company_id', 'in', company_ids)`), or ideally, add a related `company_id` field on the child model and store it for better performance.
- **`noupdate="1"`:** Always place rules inside a `<data noupdate="1">` block. Otherwise, any manual modifications to the rule by an admin in the UI will be overwritten during module upgrades.

## Verification

> 1. Log in as a user restricted to Company A.
> 2. Create a record. It should be assigned to Company A.
> 3. Switch to a user restricted to Company B.
> 4. Verify that the record created in Step 2 is not visible or accessible.
