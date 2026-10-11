# Odoo 19 Search View Group Attributes Validation Error

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `search-view`, `group`, `expand`, `validation`, `odoo19`, `rng`

---

## Problem

When defining or upgrading a module with a `<search>` view in Odoo 19 containing `<group expand="0" string="Group By">` (the standard syntax in Odoo 16, 17, and earlier), the module fails to load with an XML RelaxNG validation error:

```
odoo.tools.convert.ParseError: Element group has extra content: expand, string
Relax-NG validity error : Extra content: group in element search
```

## Root Cause

In Odoo 19, the RelaxNG schema definition for search views (`search.rng`) tightened the allowed attributes on `<group>` tags inside `<search>`. Attributes such as `expand="0"`, `expand="1"`, or `string="..."` are no longer recognized or allowed on search `<group>` elements.

## Solution ✅

Use a bare `<group>` tag inside `<search>` for `<filter name="..." string="..." context="{'group_by': '...'}"/>` definitions.

```xml
<!-- ❌ WRONG (Odoo 18 and older syntax that breaks in Odoo 19) -->
<search string="Search Visits">
    <field name="partner_id"/>
    <group expand="0" string="Group By">
        <filter name="group_by_state" string="Status" domain="[]" context="{'group_by': 'state'}"/>
    </group>
</search>

<!-- ✅ CORRECT (Odoo 19 compliant) -->
<search string="Search Visits">
    <field name="partner_id"/>
    <group>
        <filter name="group_by_state" string="Status" domain="[]" context="{'group_by': 'state'}"/>
    </group>
</search>
```

## ⚠️ Pitfalls

- Copy-pasting search views from Odoo 16/17/18 modules into Odoo 19 modules will fail during registry loading if `expand="0"` or `string="..."` is left on search groups.
- Form and List view groups still support `string="..."`, this restriction applies specifically to `<search>` view XML definitions.

## Verification

Run Odoo with module install/update:
```bash
python3 odoo-bin -c odoo.conf -d pure_integrated -u your_module --stop-after-init
```
Verify that the module loads without XML ParseError or Relax-NG validation warnings.
