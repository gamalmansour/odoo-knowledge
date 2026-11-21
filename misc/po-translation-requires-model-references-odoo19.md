# Odoo 16–19 `.po` Files Silently Ignored Without `#: model:...` Reference Comments (`trans_export` Signature in v19)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-21                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `i18n`, `ar.po`, `translations`, `trans_export`, `polib`, `odoo19`

---

## Problem

> A custom module's `i18n/ar.po` file exists and Arabic (`ar_001`) is active, yet all custom tabs, field labels, selection options, menus, and QWeb reports still render in English while Odoo core screens render in Arabic.

## Root Cause

> In Odoo 16–19 (JSONB translations), `TranslationImporter` requires exact `#: model:...`, `#: model_terms:...`, or `#: code:...` reference lines above each `msgid` so it knows which database record/table (`ir.model.fields`, `ir.model.fields.selection`, `ir.ui.view`, `ir.ui.menu`, etc.) to update. Hand-crafted `.po` entries containing only `#. module: <name>` without `#: ` references are **silently skipped**.
>
> Additionally, in **Odoo 19**:
> - CLI `--i18n-export` was removed from `odoo-bin server`.
> - `odoo.tools.translate.trans_export(lang, modules, buffer, format, env)` expects `env` as the 5th argument (NOT `env.cr`).

## Solution ✅

> Always export the exact `.pot` directly from Odoo 19 via `odoo-bin shell`, fill `msgstr` entries (e.g. via `polib`), and reload with `--i18n-overwrite`:

```python
# Step 1: Inside odoo-bin shell
from odoo.tools.translate import trans_export
with open('/tmp/module.pot', 'wb') as buf:
    trans_export(False, ['my_module'], buf, 'po', env)
```

```bash
# Step 2: Populate msgstr in i18n/ar.po preserving all #: reference lines, then reload:
./odoo-bin -c my.conf -d my_db -u my_module --i18n-overwrite --stop-after-init --no-http
```

## ⚠️ Pitfalls

- **Never omit `#: model:...` lines:** Hand-written `.po` files with bare `#. module:` + `msgid`/`msgstr` load 0 UI translations in Odoo 16–19.
- **Do not translate Python expressions:** Leave `ir.actions.report,print_report_name` entries (`'Report - %s' % (object.name)`) untranslated so PDF filename evaluation never breaks.
- **File naming:** Name the Arabic file `i18n/ar.po` (Odoo automatically loads `ar.po` for `ar_001`).

## Verification

```python
env_ar = env(context=dict(env.context, lang='ar_001'))
f = env_ar['ir.model.fields'].search([('model', '=', 'crm.lead'), ('name', '=', 'my_field')], limit=1)
print(f.field_description)  # Must print Arabic label
```
