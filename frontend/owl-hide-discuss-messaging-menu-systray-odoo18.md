# Hiding Heavy Discuss Notifications Systray Widget (`mail.messaging_menu`) in Odoo 18 OWL

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | frontend                                   |
| Odoo Versions | 17, 18                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-25                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `owl`, `systray`, `mail`, `messaging_menu`, `discuss`, `registry`, `performance`, `odoo18`

---

## Problem

On high-volume databases (for example, WhatsApp/CRM deployments with 1,900+ unread notifications or thousands of pinned channels), the top-bar Discuss Notifications systray widget (`mail.messaging_menu`) causes visible UI lag on page loads and clicks. Users still need the full **Discuss** application from the main app switcher, so uninstalling or hiding the Discuss app is not an option.

Removing the widget with CSS (`display: none`) leaves the OWL component mounted, still subscribing to mail store updates and rendering hidden DOM nodes. Trying to call `registry.category("systray").remove("mail.messaging_menu")` without forcing module load order can silently do nothing if your JS file executes before `@mail/core/public_web/messaging_menu` registers the item.

## Root Cause

In Odoo 18, `mail` registers the systray item inside `@mail/core/public_web/messaging_menu` under the key `"mail.messaging_menu"`. Asset bundle load order across custom addons is not guaranteed unless the custom ES module explicitly imports the target module first.

## Solution ✅

Create a small ES module in a standalone addon, explicitly import `@mail/core/public_web/messaging_menu` so it evaluates first, then remove the entry from `registry.category("systray")`:

**1. `static/src/js/hide_messaging_systray.js`**

```javascript
/** @odoo-module **/

import "@mail/core/public_web/messaging_menu";
import { registry } from "@web/core/registry";

/**
 * Remove the heavy Discuss Notifications systray widget while keeping
 * the Discuss application fully accessible from the main app menu.
 */
const systrayRegistry = registry.category("systray");
if (systrayRegistry.contains("mail.messaging_menu")) {
    systrayRegistry.remove("mail.messaging_menu");
}
```

**2. Register in `__manifest__.py` (with `'mail'` in `depends`)**

```python
    'depends': ['base', 'mail'],
    'assets': {
        'web.assets_backend': [
            'your_addon/static/src/js/hide_messaging_systray.js',
        ],
    },
```

## ⚠️ Pitfalls

- **Omitting `import "@mail/core/public_web/messaging_menu";`:** Without the side-effect import, `systrayRegistry.contains("mail.messaging_menu")` can evaluate to `false` depending on bundle order, leaving the icon visible.
- **Wrong module path across Odoo versions:** In Odoo 18 the path is `@mail/core/public_web/messaging_menu`; in Odoo 17 it was `@mail/core/web/messaging_menu`. Verify the exact path in `addons/mail/static/src/` before deploying on another version.
- **Forgetting `contains()` guard:** Calling `registry.remove(key)` on a missing key throws a `KeyNotFoundError` in OWL's `Registry`, which breaks backend boot.
- **CSS-only hiding:** Hiding `.o-mail-DiscussSystray-class` via CSS does not unmount the OWL component and still triggers unnecessary store reactivity.

## Verification

1. Upgrade the addon and hard-reload the Odoo backend (or run Playwright across Admin, Manager, and regular User sessions).
2. Confirm in the browser console or Playwright that `document.querySelectorAll('.o-mail-DiscussSystray-class').length === 0` with `0` JS console errors.
3. Open **Discuss** from the main app menu and confirm all channels and messages still work normally.

## References

- Odoo 18 core file: `addons/mail/static/src/core/public_web/messaging_menu.js`
- Related file: `frontend/owl_action_layout_hidden.md`
