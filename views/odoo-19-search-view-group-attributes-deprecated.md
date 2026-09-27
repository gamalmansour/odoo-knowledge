# Odoo 19 Search View: Invalid Attribute 'expand' or 'string' on <group> Tag

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `search-view`, `group-by`, `relaxng`, `odoo19`, `rng-validation`

---

## Problem

When upgrading or installing custom views in Odoo 19 with a `<search>` view containing `<group expand="0" string="Group By">`, installation fails with a `ParseError` during RelaxNG view schema validation:

```text
odoo.tools.view_validation: <string>:10:0:ERROR:RELAXNGV:RELAXNG_ERR_INVALIDATTR: Invalid attribute expand for element group
odoo.tools.view_validation: <string>:10:0:ERROR:RELAXNGV:RELAXNG_ERR_INVALIDATTR: Invalid attribute string for element group
odoo.tools.view_validation: Invalid XML: Get RNG validator and validate RNG file.
odoo.tools.convert.ParseError: while parsing ... Invalid view definition
```

Additionally, if non-stored computed fields (without a `search='...'` method) are used in `<filter domain="[...]">`, Odoo 19 immediately blocks view validation:

```text
Unsearchable field “field_name” in path “field_name” in domain of <filter name="...">
```

## Root Cause

1. **RNG Schema Change in Odoo 19:**  
   The search view RelaxNG schema (`search.rng`) in Odoo 19 removed support for `expand` and `string` attributes on `<group>` tags. Historically, `<group expand="0" string="Group By">` was common in V14–V17. In Odoo 18/19, `<group>` inside search is purely a container or group by filters can be defined directly inside `<search>` without attributes on `<group>`.

2. **Strict Domain Searchability:**  
   Odoo 19 enforces strict static validation on search filter domains. Any field referenced in a filter domain must either be stored in the database (`store=True`) or implement an explicit `search` method.

## Solution ✅

### 1. Fix Group By in Search Views

Remove `expand` and `string` attributes from `<group>`, or place `<filter>` elements with `context="{'group_by': '...'}"` directly in `<search>`:

```xml
<!-- ❌ WRONG (Odoo 14-17 legacy syntax) -->
<search string="Search Models">
    <field name="name"/>
    <group expand="0" string="Group By">
        <filter string="Salesperson" name="group_salesperson" context="{'group_by': 'user_id'}"/>
    </group>
</search>

<!-- ✅ CORRECT (Odoo 19) -->
<search string="Search Models">
    <field name="name"/>
    <separator/>
    <filter string="Salesperson" name="group_salesperson" context="{'group_by': 'user_id'}"/>
    <filter string="Category" name="group_category" context="{'group_by': 'categ_id'}"/>
</search>
```

### 2. Handle Non-Stored Computed Fields

Do not place non-stored computed fields in static `<filter domain="[...]">`. Either:
- Mark the field `store=True` if performance permits.
- Add a `search='_search_field_name'` method to the Python field definition.
- Or filter using stored relational fields or server-side actions.

## ⚠️ Pitfalls

- Running `-u` on a module with legacy search view syntax will prevent registry loading and cause server startup crashes.
- In list view inheritance on `account.move` (`view_invoice_tree`), remember that Odoo 19 uses `status_in_payment` instead of `state`.

## Verification

Run module upgrade with schema validation:
```bash
odoo-bin -c custom.conf -d pure_integrated -u my_module --stop-after-init
```
Must pass view validation with zero `RELAXNG_ERR_INVALIDATTR` errors.
