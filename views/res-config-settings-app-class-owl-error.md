# Invalid Props for Component SettingsApp: Unknown Key 'class' in Odoo 18

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 18                                         |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-09-17                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `res.config.settings`, `owl`, `settings-app`, `invalid-props`, `compiler`, `migration-v18`

---

## Problem

When opening Odoo Settings (`res.config.settings` in web client), the entire Settings page fails to render and crashes with an unhandled Owl error:

```
UncaughtPromiseError > OwlError
Uncaught Promise > Invalid props for component 'SettingsApp': unknown key 'class'
OwlError: Invalid props for component 'SettingsApp': unknown key 'class'
    at Object.validateProps (web.assets_web.min.js:1199:67)
    at SettingsFormRenderer.slot1 (<anonymous>:1383:13)
```

## Root Cause

In Odoo 18, the Settings form view compiler (`SettingsFormCompiler` in `@web/webclient/settings_form_view/settings_form_compiler.js`) compiles `<app>` XML tags into the Owl component `<SettingsApp>`:

```javascript
export class SettingsApp extends Component {
    static template = "web.SettingsApp";
    static props = {
        string: String,
        imgurl: String,
        key: String,
        selectedTab: { type: String, optional: 1 },
        slots: Object,
    };
```

In older versions of Odoo (v15/v16/v17) or third-party legacy modules (such as Webkul modules), `<app>` was often styled with CSS classes in XML:
```xml
<app class="app_settings_block o_not_app" string="My App" name="my_app">
```

Because `SettingsFormCompiler` does not declare `doNotCopyAttributes: true` for `{ selector: "app", fn: this.compileApp }`, the base `ViewCompiler` copies the `class` attribute onto the generated `<SettingsApp>` node (`<SettingsApp class="...">`). In Owl, any attribute on a Component is passed as a prop. Because `class` is not declared in `SettingsApp.props`, Owl's strict prop validation throws `Invalid props for component 'SettingsApp': unknown key 'class'`.

## Solution ✅

Remove the obsolete `class` attribute from any `<app>` tag in `res_config_settings` views:

```xml
<!-- BEFORE (Crashes in Odoo 18): -->
<app class="app_settings_block o_not_app" string="Odoo Multi Channel" name="odoo_multi_channel_sale">

<!-- AFTER (Compliant with Odoo 18): -->
<app string="Odoo Multi Channel" name="odoo_multi_channel_sale">
```

If the app should be hidden when not installed or marked as not a standalone app, use the official `notApp="1"` attribute instead of CSS classes:
```xml
<app notApp="1" string="Sales" name="sale_management">
```

After modifying the XML, upgrade the module to reload the view:
```bash
./odoo-bin -c odoo.conf -u <module_name> --stop-after-init
```

## ⚠️ Pitfalls

- Even if the broken `<app>` tag belongs to another module (e.g. multi-channel integration), opening ANY settings page (General Settings, POS Settings, Sale Settings) will fail because `res.config.settings` combines all installed apps into one global form view.
- Never add custom attributes to `<app>` tags that are not part of `SettingsApp.props` (`string`, `imgurl`, `name`/`key`, `notApp`).

## Verification

1. Check for any remaining `<app.*class=` tags in the codebase:
```bash
grep -rn "<app.*class" addons/ custom/
```
2. Navigate to **Settings** in the web client. The page must load without any Owl prop validation errors.
