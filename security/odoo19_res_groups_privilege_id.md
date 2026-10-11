# Odoo 19 `res.groups` category_id and users Fields Removed

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade / security                         |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-07-05                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo19`, `security`, `res.groups`, `category_id`, `privilege_id`, `users`, `user_ids`

---

## Problem

> When installing or upgrading a module with custom security groups in Odoo 19, you encounter `ValueError` during XML parsing because `category_id` and `users` are no longer valid fields in `res.groups`.

```
ValueError: Invalid field 'category_id' in 'res.groups'
# AND
ValueError: Invalid field 'users' in 'res.groups'
```

## Root Cause

> 1. `category_id` has been removed from `res.groups`. Instead, groups are categorized via `privilege_id`, which links to a new model `res.groups.privilege`. The `res.groups.privilege` model then links to `ir.module.category`.
> 2. `users` field alias has been strictly removed or enforced as `user_ids` in Odoo 19 XML data loading.

## Solution ✅

> 1. Create a `res.groups.privilege` record linking to your `ir.module.category`.
> 2. Change the `category_id` field on your `res.groups` record to `privilege_id`, and reference your new `res.groups.privilege` record.
> 3. Change `<field name="users" ...>` to `<field name="user_ids" ...>` and optionally use the new `Command.link()` syntax instead of the legacy `(4, ...)` tuple.

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

<!-- Step 3: Use privilege_id and user_ids on the group -->
<record id="group_custom" model="res.groups">
    <field name="name">Custom Group</field>
    <field name="privilege_id" ref="res_groups_privilege_custom"/> <!-- CHANGED HERE -->
    <field name="user_ids" eval="[Command.link(ref('base.user_root'))]"/> <!-- CHANGED HERE -->
</record>
```

## ⚠️ Pitfalls

- Forgetting to create the `res.groups.privilege` record will cause reference errors.
- Continuing to use `<field name="users">` will crash the module install immediately. Use `user_ids`.

## Verification

> Install the module in Odoo 19. It should parse successfully without raising any `ValueError` on `category_id` or `users`.
