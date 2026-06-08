# Missing `oe_title` Class in Odoo 19 `res.partner` Base View

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 19                                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-06-08                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `xpath`, `res.partner`, `oe_title`, `ParseError`, `Odoo 19`

---

## Problem

> When upgrading a module to Odoo 19 that inherits from `base.view_partner_form`, you may encounter an XML ParseError indicating that the `div` with class `oe_title` cannot be located.

```
odoo.tools.convert.ParseError: while parsing /path/to/view.xml:3
Error while parsing or validating view:

Element '<xpath expr="//div[hasclass('oe_title')]">' cannot be located in parent view
```

## Root Cause

> In Odoo 19, the structure of the base `res.partner` form view (`base.view_partner_form`) has been refactored. The `div class="oe_title"` may no longer exist as a single unique wrapper or its structure was changed in a way that standard XPath queries relying on it fail.

## Solution ✅

> Instead of relying on `//div[hasclass('oe_title')]`, target a more stable element such as the `h1` tag that wraps the partner's name. Use `[1]` to ensure you are targeting the first `h1` element in case there are multiple.

```xml
<!-- Avoid this in Odoo 19 -->
<xpath expr="//div[hasclass('oe_title')]" position="inside">
    <!-- fields -->
</xpath>

<!-- Do this instead -->
<xpath expr="//h1[1]" position="after">
    <!-- fields -->
</xpath>
```

## ⚠️ Pitfalls

- Using `//h1` without `[1]` might still cause issues if another module or a future Odoo update introduces a second `h1` element in the form view. Always index `[1]` to be safe.
- Do not assume `oe_title` exists in other base models in Odoo 19 either; always check the base view source code first.

## Verification

> Perform a module upgrade after changing the XPath. It should complete without `ParseError`.

```bash
odoo-bin -u your_module_name
```
