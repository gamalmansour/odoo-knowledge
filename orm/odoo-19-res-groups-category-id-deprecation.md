# Odoo 19 res.groups category_id Deprecation

## Problem 🔴
When creating a custom security group (`res.groups`) in Odoo 19 and assigning an `ir.module.category` using the `category_id` field in XML, an installation error occurs:
`ValueError: Invalid field 'category_id' in 'res.groups'`

## Cause ⚠️
Odoo 19 fundamentally changed how groups are categorized. The `category_id` field was completely removed from the `res.groups` model. Instead, Odoo 19 introduces a new model `res.groups.privilege`. Groups are now linked to categories via the `privilege_id` field.

## Solution ✅

**Quick fix:** remove `category_id` from the `<record model="res.groups">` —
the group installs fine and lands under "Other" in the user form.

**Proper fix (own section in the user form, verified live):** Odoo 19 groups
are sectioned through `res.groups.privilege` (which itself points to an
`ir.module.category`). Create category → privilege → point the groups at the
privilege. Chained groups (implied_ids ladder) under ONE privilege render as
a single **level dropdown** in the user form — e.g. Discount Approval:
Supervisor / Sales Manager / Company Director:

```xml
<record id="module_category_solargy" model="ir.module.category">
    <field name="name">Solargy</field>
    <field name="sequence">57</field>
</record>

<record id="res_groups_privilege_discount_approval" model="res.groups.privilege">
    <field name="name">Discount Approval</field>
    <field name="sequence">10</field>
    <field name="category_id" ref="module_category_solargy"/>
</record>

<record id="group_discount_supervisor" model="res.groups">
    <field name="name">Supervisor</field>
    <field name="privilege_id" ref="res_groups_privilege_discount_approval"/>
</record>
<!-- higher tiers: same privilege_id + implied_ids chain -->
```

Verification SQL after install:
```sql
SELECT g.name->>'en_US', p.name->>'en_US', c.name->>'en_US'
FROM res_groups g
LEFT JOIN res_groups_privilege p ON p.id = g.privilege_id
LEFT JOIN ir_module_category c ON c.id = p.category_id
WHERE g.id IN (SELECT res_id FROM ir_model_data WHERE module='<module>' AND model='res.groups');
```

**Naming tip:** with a privilege the UI shows `<privilege>: <group>` — name
the groups bare ("Supervisor"), not "Discount Approval: Supervisor", or the
label doubles up.

**Incorrect (Odoo 18 and below):**
```xml
<record id="group_custom" model="res.groups">
    <field name="name">Custom Group</field>
    <field name="category_id" ref="module_category_custom"/>
</record>
```

## Odoo Version
Odoo 19+

## Last Verified
2026-08-04 (privilege recipe verified in solargy_sale_approval 19.0.3.1.0)
