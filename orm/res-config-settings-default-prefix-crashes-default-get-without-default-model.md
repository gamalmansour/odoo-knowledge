# `res.config.settings` Field Starting with `default_` Crashes Settings UI (`without attribute 'default_model'`)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19 (All)                   |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `res.config.settings`, `default_get`, `default_model`, `related`, `settings`, `owl`, `playwright`

---

## Problem

> A company-scoped configuration field on `res.company` (e.g., `default_center_location`) is exposed on `res.config.settings` using the same field name (`default_center_location = fields.Char(related='company_id.default_center_location', readonly=False)`).
>
> Module installation (`-i` / `-u`), XML view validation (`get_views()`), and backend `TransactionCase` tests writing to `res.company` all pass 100%. However, the instant any user opens **Settings** in the browser (`onchange` -> `res.config.settings.default_get()`), the entire Settings app crashes with an `RPC_ERROR` / `OwlError`:

```
File "odoo/addons/base/models/res_config.py", line 427, in _get_classified_fields
    raise Exception("Field %s without attribute 'default_model'" % field)
Exception: Field res.config.settings.default_center_location without attribute 'default_model'
```

## Root Cause

> `res.config.settings._get_classified_fields()` classifies fields strictly by **name prefix** BEFORE checking `related=` or standard fields:
> 1. `default_*` -> treated as an `ir.default` setter requiring `default_model='target.model'` (writes `ir.default.set(default_model, name[8:], value)`).
> 2. `group_*` -> treated as a `res.groups` toggle requiring `implied_group='...'`.
> 3. `module_*` -> treated as an `ir.module.module` installer toggle (`boolean` or `selection`).
>
> Because `_get_classified_fields()` is only invoked inside `res.config.settings.default_get()` and `execute()` (not during registry build or `get_views()`), a `related='company_id.default_*'` field passes module installation silently and breaks **every** Settings page in the ERP at runtime.

## Solution ✅

> Never name a `related='company_id.*'` or `config_parameter=` field on `res.config.settings` with the reserved prefixes `default_`, `group_`, or `module_`. Keep the descriptive name on `res.company` if desired, and use a non-reserved name on `res.config.settings`:

```python
class ResCompany(models.Model):
    _inherit = 'res.company'

    default_center_location = fields.Char(string='Default Training Location', translate=True)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Avoid reserved 'default_' prefix on res.config.settings!
    center_default_location = fields.Char(
        related='company_id.default_center_location',
        readonly=False,
    )
```

```xml
<label for="center_default_location" class="col-lg-4 o_light_label"/>
<field name="center_default_location" class="col-lg-8"/>
```

## ⚠️ Pitfalls

- **`get_views()` does NOT catch this:** Calling `env['res.config.settings'].get_views([(False, 'form')])` only compiles the XML arch; it does not call `default_get()` or `onchange()`. Always test `env['res.config.settings'].create({})` in Python tests AND open Settings in Playwright (`webapp-testing`) to verify OWL rendering.
- **Same trap applies to `group_*` and `module_*`:** Naming a `related=` field `group_discount_rate` or `module_title` on `res.config.settings` triggers the exact same `_get_classified_fields` crash.
- **Playwright `/web` waiting tip:** Never use `wait_for_load_state("networkidle")` on Odoo 17+ `/web` or logged-in `/my` pages, because Odoo opens a persistent `/websocket` bus connection that prevents `networkidle` from resolving. Wait on `domcontentloaded` + `.o_main_navbar` + `.o_loading_indicator` hidden instead.

## Verification

```bash
# Open Settings in headless Chromium via Playwright and assert zero .o_error_dialog
/Users/gamal/odoo/odoo17.0/.venv/bin/python3 tests_e2e/run_e2e.py --tier 2 --port 9998 --gevent-port 8718
```

## References

- Odoo Core: `odoo/addons/base/models/res_config.py` (`ResConfigSettings._get_classified_fields`)
- Related file: `views/res-config-settings-orphan-fields-leak.md`
