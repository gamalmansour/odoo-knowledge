# `View inheritance may not use attribute 'string' as a selector` — xpath on `group[@string=...]` Aborts the Whole Module

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-23                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `xpath`, `inheritance`, `string`, `selector`, `ParseError`

---

## Problem

Targeting a `<group string="Controls">` (or a page/notebook) by its label in an inherited view:

```xml
<xpath expr="//page[@name='project_settings']/group[@string='Controls']" position="inside">
    <field name="auto_generate_work_orders"/>
</xpath>
```

crashes the whole module install/upgrade:

```
odoo.tools.convert.ParseError: while parsing .../my_views.xml:5
Error while parsing or validating view:
View inheritance may not use attribute 'string' as a selector.
```

## Root Cause

`string` is a **translatable** attribute. If xpath could match on it, the same inheriting view would break the moment the base view is viewed in another language (the label no longer matches). Odoo forbids `string` as an inheritance selector by design — it is not a parse typo, it is a hard rule.

## Solution ✅

Anchor on something **stable and non-translatable**: a `name`, a field inside the target, or a structural position.

```xml
<!-- Anchor on a field that lives inside the group -->
<xpath expr="//page[@name='project_settings']//field[@name='qty_control_policy']" position="after">
    <field name="auto_generate_work_orders"/>
</xpath>
```

Preference order for anchors:
1. `name` — `//page[@name='x']`, `//field[@name='y']`, `//button[@name='z']` (best: stable + unique).
2. A child `field[@name=...]` with `position="after"/"before"`.
3. Structural: `//notebook/page[3]` (brittle — avoid unless nothing has a name).

If you own the base view and genuinely need the group as an anchor, give it a `name`:
`<group name="controls" string="Controls">` then `//group[@name='controls']`.

## ⚠️ Pitfalls

- Same rule applies to any translatable attribute (`string`, `help`, `sum`, `confirm`) — never use them as selectors.
- The error names the INHERITING view, not the attribute location — read the `expr` in that view's xpaths.
- It is fatal at load: one bad selector takes down the entire module (and anything depending on it), so it surfaces as a CRITICAL "Failed to initialize database", not a warning.

## Verification

```bash
./odoo-bin -c <conf> -d <db> -u <module> --stop-after-init
```

## References

- Hit in `construction_project` v17.0.1.22.0 — `views/project_auto_generation_views.xml` (adding two profile flags into the base `construction.profile` form's Controls group)
- Related file: `views/xml-load-order-manifest.md`
