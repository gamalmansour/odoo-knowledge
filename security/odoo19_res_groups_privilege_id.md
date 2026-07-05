# Odoo 19 `res.groups` category_id Removed (Replaced by privilege_id)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade / security                         |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-07-05                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo19`, `security`, `res.groups`, `category_id`, `privilege_id`

---

## Problem

> When installing or upgrading a module with custom security groups in Odoo 19, you encounter a `ValueError` during XML parsing because `category_id` is no longer a valid field in `res.groups`.

```
ValueError: Invalid field 'category_id' in 'res.groups'
odoo.tools.convert.ParseError: while parsing ...
```

## Root Cause

> In Odoo 19, the `category_id` field has been removed from `res.groups`. Instead, groups are categorized via `privilege_id`, which links to a new model `res.groups.privilege`. The `res.groups.privilege` model then links to `ir.module.category`.

## Solution ✅

> 1. Create a `res.groups.privilege` record linking to your `ir.module.category`.
> 2. Change the `category_id` field on your `res.groups` record to `privilege_id`, and reference your new `res.groups.privilege` record.

```xml
<!-- Step 1: Define the category (same as before) -->
<record id="module_category_custom" model="ir.module.category">
    <field name="name">Custom Category</field>
</record>

<!-- Step 2: Define the Privilege -->
<record model="res.groups.privilege" id="res_groups_privilege_custom">
    <field name="name">Custom Category Privilege</field>
    <field name="category_id" ref="module_category_custom"/>
</record>

<!-- Step 3: Use privilege_id instead of category_id on the group -->
<record id="group_custom" model="res.groups">
    <field name="name">Custom Group</field>
    <field name="privilege_id" ref="res_groups_privilege_custom"/> <!-- CHANGED HERE -->
</record>
```

## ⚠️ Pitfalls

- Forgetting to create the `res.groups.privilege` record will cause reference errors.
- If you're building a multi-version module, you'll need conditional XML or separate security files for Odoo 19 vs. older versions.

## Verification

> Install the module in Odoo 19. It should parse successfully without raising the `ValueError` on `category_id`.
