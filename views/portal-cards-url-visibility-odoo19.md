# Odoo 19 Portal Cards Visibility URL Matching

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 19                                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-06-28                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `portal`, `qweb`, `views`, `url`, `startswith`, `visibility`, `odoo19`

---

## Problem

> When trying to hide standard Odoo portal cards (like Orders, Invoices, Addresses, Security) by wrapping or overriding `portal.portal_docs_entry` and matching the `url` variable, the exact match (`url == '/my/invoices'`) fails in Odoo 19. The cards remain visible even when the condition should hide them.

## Root Cause

> In Odoo 19, some standard portal cards append query parameters to the URL passed to `portal_docs_entry`. For example, the Invoices card uses `/my/invoices?filterby=invoices` and Bills uses `/my/invoices?filterby=bills`. An exact equality check `url == '/my/invoices'` will evaluate to `False`.
> Additionally, note that the standard Addresses card URL is `/my/addresses`, not `/my/account`.

## Solution ✅

> Use `url and url.startswith(...)` instead of exact equality (`url == ...`) when injecting visibility conditions into `portal.portal_docs_entry`.

```xml
<template id="portal_docs_entry_visibility" inherit_id="portal.portal_docs_entry" priority="100">
    <xpath expr="." position="attributes">
        <attribute name="t-if">not (
            (url and url.startswith('/my/orders') and not request.env.user.show_portal_orders) or
            (url and url.startswith('/my/invoices') and not request.env.user.show_portal_invoices) or
            (url and url.startswith('/my/addresses') and not request.env.user.show_portal_addresses) or
            (url and url.startswith('/my/security') and not request.env.user.show_portal_security)
        )</attribute>
    </xpath>
</template>
```

## ⚠️ Pitfalls

- Using exact string match `url == '/my/invoices'` will fail and the card will remain visible.
- Always ensure you check if `url` exists first (`url and url.startswith()`) since some custom third-party portal cards might not set the `url` variable before calling `portal_docs_entry`.
- Using `/my/account` for addresses will not match. Use `/my/addresses` for the addresses card and `/my/security` for the "Connection & Security" card.

## Verification

> Check the portal home view with a user that has the toggles disabled. Ensure that both Invoices and Bills disappear properly.
