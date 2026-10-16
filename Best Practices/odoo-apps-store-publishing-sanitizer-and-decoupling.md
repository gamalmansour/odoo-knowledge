# Odoo Apps Store (`apps.odoo.com`) HTML Sanitizer & Standalone Module Decoupling

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | All (15, 16, 17, 18, 19)                   |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-16                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `apps.odoo.com`, `index.html`, `sanitizer`, `post_init_hook`, `standalone`, `marketplace`

---

## Problem

When publishing custom modules to the Odoo Apps Store (`apps.odoo.com`), two critical failures frequently happen:
1. **Broken Store Landing Page (`static/description/index.html`):** Store pages lose all styling, CSS variables, gradients, and external Google Fonts, leaving plain unformatted text.
2. **Fresh-DB Install Crash (`post_init_hook` & Vertical Coupling):** Modules extracted from vertical ERP suites (e.g., Construction or Contracting) crash during automated Apps Store testing or fresh database installation because `post_init_hook` assumes a Chart of Accounts (`account.account`, `account.journal`) is already installed, or models reference vertical-only models (`construction.project`, `contract.owner`) not in standard Odoo.

## Root Cause

1. **Odoo Apps Store HTML Sanitizer:** `apps.odoo.com` runs a strict HTML sanitizer on `static/description/index.html` that strips `<head>`, `<style>`, `<link>`, `<script>`, CSS variables (`var(--...)`), and custom classes not in Bootstrap / FontAwesome 4 (`fa fa-*`).
2. **Pre-CoA Module Installation:** When a user installs an accounting add-on on a brand-new database before selecting a localization/Chart of Accounts package, `account.account` and `account.journal` tables are empty. Any `post_init_hook` attempting to create or bind default accounts fails or creates orphan accounts.

## Solution ✅

### 1. 100% Inline CSS + Bootstrap Grid + FontAwesome 4 in `static/description/index.html`
- Never use `<style>` blocks or `<link>` tags in `static/description/index.html`.
- Put all styling inside inline `style="..."` attributes on `<section>`, `<div>`, `<h2>`, `<p>`, and `<span>` elements.
- Use only FontAwesome 4 classes (`fa fa-check-circle`, `fa fa-shield`, `fa fa-cogs`, etc.).

### 2. Replace `post_init_hook` Account Seeding with an On-Demand Settings Action
- Do **not** run automatic Chart of Accounts seeding in `post_init_hook`.
- Provide an idempotent helper method on `res.company` (e.g., `_auto_configure_custody_accounts()`) and expose it via a button in `res.config.settings` (`action_auto_configure_custody`) plus an `ir.actions.server` record so administrators can run it after their Chart of Accounts is installed.

### 3. Decouple Vertical Models into Standard Odoo Models
- Replace custom project models with standard `project.project` (`project_id`) and `account.analytic.account` (`analytic_account_id`, computed from `project_id.account_id` with `store=True, readonly=False`).
- Split monolithic industry modules into focused single-responsibility modules (e.g., `account_custody_management` for Employee Cash Custody and `account_bank_guarantee` for Letters of Guarantee).

## ⚠️ Pitfalls

- **Never leave legacy model names in `ir.model.access.csv` or `demo/*.xml`:** After renaming models for generic market appeal, validate every XML `model="..."`, `res_model`, and sequence `code` via AST/ElementTree parsing.
- **Multi-Currency Journal Entries in Wizards:** Ensure modification/extension wizards pass generated journal entry line dicts through the parent model's multi-currency conversion helper (`_apply_fx_to_lines`) before calling `env['account.move'].create()`.

## Verification

```bash
# Verify no <style> or <link> tags exist in static/description/index.html
grep -iE "<style|<link" static/description/index.html || echo "Clean inline HTML!"
```

## References

- Related modules: `account_custody_management`, `account_bank_guarantee`
