# XPath hasclass() fails on Portal Cards in Odoo 19

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 19                                         |
| Severity      | 🟡 Medium                                   |
| Last Verified | 2026-06-28                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `xpath`, `qweb`, `portal`, `hasclass`, `odoo19`

---

## Problem

> When trying to inherit and modify `portal.portal_docs_entry` to target the card element, using `hasclass('o_portal_index_card')` raises a `ParseError` stating the element cannot be located in the parent view.

```
Error while parsing or validating view:
Element '<xpath expr="//div[hasclass('o_portal_index_card')]">' cannot be located in parent view
```

## Root Cause

> In Odoo 19, the `class` attribute of the portal card in `portal_docs_entry` was changed from a static `class="o_portal_index_card"` to a dynamic `t-att-class="'o_portal_index_card ' + ... "`. 
> The `hasclass()` XPath function in Odoo only evaluates static string literals in `class` or `t-attf-class` attributes, so it fails to match dynamic `t-att-class` attributes.

## Solution ✅

> Instead of targeting the class, target the element structure directly. Since the card is the main `<div>` wrapper inside the `portal_docs_entry` template, you can target it positionally.

```xml
<!-- Avoid this in Odoo 19 -->
<xpath expr="//div[hasclass('o_portal_index_card')]" position="attributes">

<!-- Use this instead -->
<xpath expr="//div[1]" position="attributes">
```

## ⚠️ Pitfalls

- This dynamic class issue might affect other base Odoo templates upgraded to Odoo 19. If `hasclass()` suddenly stops working after an upgrade, check the base view to see if `class` was replaced with `t-att-class`.
