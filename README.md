# 🧠 Odoo Knowledge Base

> A shared, evolving knowledge base for solving recurring Odoo development and DevOps challenges.
> Used by both **humans** and **AI agents** (Antigravity / Gemini) to avoid repeating mistakes.

## 📖 How to Use

- **Developers:** Browse the index below or search by tags to find solutions.
- **AI Agents:** Read this `README.md` FIRST at the start of every task. Check if the problem has been solved before. See `CONTRIBUTING.md` for full workflow.

---

## 📂 Categories

| Folder | Description |
|---|---|
| `setup/` | Installation, configuration, environment, dependencies |
| `orm/` | Models, fields, ORM methods, computed fields, constraints |
| `views/` | XML views, OWL components, QWeb, JS widgets |
| `security/` | Access rights, record rules, groups, multi-company |
| `performance/` | Query optimization, caching, indexing, profiling |
| `deployment/` | Server config, Nginx, SSL, Docker, production |
| `upgrade/` | Version migration, data migration, breaking changes |
| `misc/` | Anything that doesn't fit above |

---

## 📋 Knowledge Index

### Setup

| # | File | Severity | Versions | Tags | Description |
|---|------|----------|----------|------|-------------|
| 1 | [lxml-build-failure-python313-plus.md](setup/lxml-build-failure-python313-plus.md) | 🔴 Critical | 17, 18, 19 | `lxml`, `python`, `build`, `gcc` | lxml fails to compile on Python 3.13+ due to incompatible pointer types with newer libxml2 headers |
| 2 | [wkhtmltopdf-not-in-ubuntu-repos.md](setup/wkhtmltopdf-not-in-ubuntu-repos.md) | 🔴 Critical | All | `wkhtmltopdf`, `pdf`, `ubuntu`, `apt` | wkhtmltopdf removed from Ubuntu 24.04+ repos, must install from GitHub .deb |
| 3 | [python-version-compatibility.md](setup/python-version-compatibility.md) | 🔴 Critical | All | `python`, `version`, `venv` | Each Odoo version supports specific Python versions — full compatibility matrix |
| 4 | [system-dependencies-ubuntu.md](setup/system-dependencies-ubuntu.md) | 🔴 Critical | All | `apt`, `dependencies`, `libpq`, `libldap` | Required apt packages before pip install (libpq-dev, libldap2-dev, etc.) |
| 5 | [multi-version-odoo-setup.md](setup/multi-version-odoo-setup.md) | 🟡 Medium | All | `venv`, `database`, `ports`, `multi-version` | Strategy for running 5 Odoo versions on one machine (folder structure, ports, databases) |
| 6 | [vscode-auto-activate-venv.md](setup/vscode-auto-activate-venv.md) | 🟢 Low | All | `vscode`, `antigravity`, `terminal`, `venv` | Auto-activate venv in Antigravity terminal using custom rcfile |
| 7 | [gevent-slow-compilation.md](setup/gevent-slow-compilation.md) | 🟢 Low | All | `gevent`, `greenlet`, `compilation`, `slow` | gevent/greenlet take 2-5 min to build on new Python — this is normal |
| 8 | [missing-python-dependency-pandas.md](setup/missing-python-dependency-pandas.md) | 🔴 Critical | All | `pandas`, `dependency`, `pip` | Missing python pandas dependency causes crash on startup / registry loading during import scan |
| 9 | [missing-rtlcss-css-error.md](setup/missing-rtlcss-css-error.md) | 🔴 Critical | All | `rtlcss`, `css`, `arabic`, `ui`, `setup`, `nodejs` | Missing rtlcss global npm package causes Arabic UI layout to break with "A css error occured" |
| 10 | [odoo-setup-automator-risks.md](setup/odoo-setup-automator-risks.md) | 🔴 Critical | All | `automation`, `setup`, `risks` | Pre-mortem risk analysis for the internal Odoo.sh Setup Automator GUI tool (database wipes, SSH hangs, disk space) |
| 11 | [postgresql-port-conflict-and-db-version-mismatch.md](setup/postgresql-port-conflict-and-db-version-mismatch.md) | 🔴 Critical | 17, 18, 19 | `postgresql`, `port-conflict`, `startup`, `database`, `version-mismatch`, `short_time_format`, `brew`, `macos` | PostgreSQL port 5432 conflict between multiple installed versions on macOS, and DB version mismatch causing missing column errors on startup |
| 12 | [csrf-session-conflict-multi-instance.md](setup/csrf-session-conflict-multi-instance.md) | 🔴 Critical | All | `csrf`, `session`, `multi-instance`, `localhost`, `cookie`, `bad-request`, `400` | CSRF token / session conflict when running multiple Odoo instances simultaneously on the same machine |
| 13 | [data-addons-write-permissions.md](setup/data-addons-write-permissions.md) | 🔴 Critical | All | `setup`, `permissions`, `data_dir`, `assets`, `AssetsLoadingError` | Data Addons directory write permission issues causing AssetsLoadingError |
| 14 | [pgvector-postgresql-extension-required-for-ai-module.md](setup/pgvector-postgresql-extension-required-for-ai-module.md) | 🔴 Critical | 17, 18, 19 | `pgvector`, `postgresql`, `ai`, `enterprise`, `vector`, `embedding`, `extension` | pgvector PostgreSQL extension required for Odoo Enterprise AI module (RAG/embeddings) — setup for macOS, Linux, Odoo.sh |

### ORM

| # | File | Severity | Versions | Tags | Description |
|---|------|----------|----------|------|-------------|
| 1 | [extending-selection-fields-safely.md](orm/extending-selection-fields-safely.md) | 🟡 Medium | All | `orm`, `selection`, `fields`, `inheritance` | Safely extending selection fields in Odoo without breaking original core options |
| 2 | [prevent-qty-moved-exceeding-qty-constraint.md](orm/prevent-qty-moved-exceeding-qty-constraint.md) | 🔴 Critical | 18 | `orm`, `constraint`, `validation`, `related-field` | Prevent qty_moved from exceeding actual qty in warehouse transactions via dynamic constraints and readonly form state |
| 3 | [partner-outstanding-due-amount-calculation-odoo.md](orm/partner-outstanding-due-amount-calculation-odoo.md) | 🟢 Low | All | `orm`, `partner`, `due-amount`, `credit`, `debit` | Computed res.partner due_amount field and drilldown stat button to unpaid invoices |
| 4 | [forwarding-carrier-banking-info-refund-request.md](orm/forwarding-carrier-banking-info-refund-request.md) | 🟡 Medium | 17, 18, 19 | `orm`, `refund`, `credit-note`, `carrier`, `banking` | Forwarding carrier and banking info from Sale Order to Refund Request & Credit Note |
| 5 | [automatic-invoice-reconciliation-customer-advances.md](orm/automatic-invoice-reconciliation-customer-advances.md) | 🟡 Medium | 17, 18, 19 | `orm`, `account`, `reconciliation`, `invoice`, `customer-advance` | Automatic reconciliation of customer invoice with intermediate advances/gateway payment entries |
| 6 | [o2c-project-phase-workflow-pattern.md](orm/o2c-project-phase-workflow-pattern.md) | 🟡 Medium | 19 | `orm`, `project`, `workflow`, `selection`, `statusbar`, `write-override` | O2C lifecycle phase workflow with clickable statusbar, write() validation, milestone-to-invoice auto-tracking |
| 7 | [o2c-phase-validations.md](orm/o2c_phase_validations.md) | 🟡 Medium | 17, 18, 19 | `orm`, `architecture`, `o2c`, `validation`, `state-machine` | Centralizing O2C phase validations to prevent spaghetti code |
| 8 | [hr-payroll-master-report-waiting-payslips.md](orm/hr-payroll-master-report-waiting-payslips.md) | 🟢 Low | 16, 17, 18, 19 | `orm`, `hr_payroll`, `master-report`, `payslip`, `localization` | Overriding HR Payroll Master Report to include Waiting (Verify) payslips in localizations |
| 9 | [bypass-record-rules-duplicate-validation.md](orm/bypass-record-rules-duplicate-validation.md) | 🔴 Critical | All | `orm`, `security`, `validation`, `duplicates`, `sudo` | Securely bypassing record rules for duplicate checks via sudo().search_read() without N+1 query bottlenecks |
| 10 | [odoo-19-res-groups-category-id-deprecation.md](orm/odoo-19-res-groups-category-id-deprecation.md) | 🔴 Critical | 19 | `orm`, `security`, `groups`, `res.groups`, `category_id` | Resolves ValueError: Invalid field 'category_id' when creating custom security groups in Odoo 19 |
| 11 | [compute-cache-warnings-ast.md](orm/compute_cache_warnings_ast.md) | 🔴 Critical | 17 | `orm`, `compute`, `cache`, `store`, `compute_sudo` | Resolves cache warnings when multiple fields share a compute method by consistently assigning store and compute_sudo using AST |
| 12 | [pos-single-screen-checkout-owl.md](orm/pos-single-screen-checkout-owl.md) | 🟢 Easy | 17, 18 | `pos`, `owl`, `quick-checkout`, `payment`, `numpad` | Combine ProductScreen and PaymentScreen into a unified checkout interface with shared Numpad |
| 11 | [pos-advanced-employee-ids-forced-readd.md](orm/pos-advanced-employee-ids-forced-readd.md) | 🟡 Medium | 18, 19 | `pos`, `pos_hr`, `advanced_employee_ids`, `many2many`, `write-override`, `sql` | POS administrators forcefully re-added to advanced_employee_ids on every save, bypassed via SQL on M2M join table |
| 12 | [avoid-translation-in-field-definitions.md](orm/avoid-translation-in-field-definitions.md) | 🔴 Critical | All | `translation`, `i18n`, `fields`, `_()`, `class-body`, `bug` | Do NOT use `_()` inside field `string=`/`help=` definitions — evaluated at import time, translations silently ignored |
| 13 | [write-override-atomicity-pattern.md](orm/write-override-atomicity-pattern.md) | 🔴 Critical | All | `write`, `override`, `atomicity`, `state-machine`, `transaction` | State changes on related records must happen AFTER `super().write()` to guarantee atomicity |
| 14 | [link-employee-fleet-to-partner-for-invoicing.md](orm/link-employee-fleet-to-partner-for-invoicing.md) | 🟢 Low | All | `orm`, `partner`, `invoice`, `vendor-bill` | Explicitly linking HR Employee and Fleet Vehicle to a Partner for Vendor Bill creation to avoid UserErrors |
| 15 | [related-field-keyerror-reference.md](orm/related-field-keyerror-reference.md) | 🔴 Critical | All | `orm`, `related`, `fields`, `keyerror` | KeyError when a related field traverses through a target field that does not exist or has a typo |
| 16 | [constrains-inherited-models-conditional.md](orm/constrains-inherited-models-conditional.md) | 🔴 Critical | All | `orm`, `constrains`, `inheritance`, `validation` | api.constrains on inherited models blocking normal operations unless scoped conditionally |
| 17 | [partner-level-visit-constraints.md](orm/partner-level-visit-constraints.md) | 🟡 Medium | All | `orm`, `visit`, `constraints`, `partner` | Move business constraints tightly coupled with product counts to res.partner level to avoid loopholes |
| 18 | [architecture-circular-dependency-mixin.md](orm/architecture-circular-dependency-mixin.md) | 🔴 Critical | 15+ | `orm`, `architecture`, `dependencies`, `mixin` | Resolves TypeError inherits from non-existing model caused by circular dependencies when adding context to base mixins |
### Views

| # | File | Severity | Versions | Tags | Description |
|---|------|----------|----------|------|-------------|
| 1 | [wkhtmltopdf-report-overlapping-header-columns.md](views/wkhtmltopdf-report-overlapping-header-columns.md) | 🟡 Medium | 17, 18, 19 | `wkhtmltopdf`, `qweb`, `report`, `bootstrap`, `overlap` | Legacy col-auto and mw-100 column classes inside report informations row cause text to overlap in newer Odoo versions |
| 2 | [qweb-report-zebra-striping-and-colspan.md](views/qweb-report-zebra-striping-and-colspan.md) | 🟡 Medium | All | `qweb`, `report`, `bootstrap`, `zebra-striping`, `colspan` | QWeb report table zebra-striping removal and table alignment/colspan issues |
| 3 | [tree-view-column-invisible-odoo17-18.md](views/tree-view-column-invisible-odoo17-18.md) | 🟡 Medium | 17, 18, 19 | `views`, `tree`, `list`, `invisible`, `column_invisible` | Migrating invisible to column_invisible inside tree/list view fields in Odoo 17 & 18 |
| 4 | [owl-custom-many2one-navigation-widget-odoo18.md](views/owl-custom-many2one-navigation-widget-odoo18.md) | 🟡 Medium | 17, 18, 19 | `owl`, `javascript`, `many2one`, `widget`, `navigation` | Custom OWL field widget acting like open_move_widget for Many2one fields in Odoo 18 |
| 5 | [separate-invoice-line-description-odoo18.md](views/separate-invoice-line-description-odoo18.md) | 🟡 Medium | 18, 19 | `views`, `invoice`, `widget` | Revert merged invoice line description to show it as separate column next to product |
| 6 | [qweb-report-display-type-odoo17-18.md](views/qweb-report-display-type-odoo17-18.md) | 🔴 Critical | 17, 18, 19 | `qweb`, `report`, `display_type` | Fix for empty invoice lines in custom prints after migrating to Odoo 17 or 18 due to display_type changes |
| 7 | [prevent-manual-editing-one2many-modal.md](views/prevent-manual-editing-one2many-modal.md) | 🟡 Medium | All | `views`, `one2many`, `readonly`, `ui`, `modal` | Prevent users from manually editing records via the default One2many popup modal by applying readonly to the field |
| 8 | [xml-load-order-manifest.md](views/xml-load-order-manifest.md) | 🔴 Critical | All | `manifest`, `xml`, `load order`, `parent menu`, `external id` | Manifest XML file load order issues causing External ID not found during installation/upgrade |
| 9 | [oe_title-missing-odoo19-res-partner.md](views/oe_title_missing_odoo19_res_partner.md) | 🟡 Medium | 19 | `xpath`, `res.partner`, `oe_title`, `ParseError`, `Odoo 19` | Missing `oe_title` class in Odoo 19 `res.partner` base view causing ParseError when migrating module views |
| 10 | [widget-vs-field-tag-odoo17.md](views/widget-vs-field-tag-odoo17.md) | 🔴 Critical | 16, 17, 18, 19 | `views`, `kanban`, `widget`, `field` | Field widgets declaration in Kanban views using field tag with widget attribute |
| 11 | [section_and_note_one2many_empty_row_bug.md](views/section_and_note_one2many_empty_row_bug.md) | 🔴 Critical | 16, 17, 18, 19 | `views`, `one2many`, `section_and_note_one2many`, `ui`, `tree`, `required` | section_and_note_one2many widget creates empty/deleted rows and raises RPC validation errors when dragging |
| 12 | [inherited_view_groups_constraint_error.md](views/inherited_view_groups_constraint_error.md) | 🔴 Critical | 18, 19 | `views`, `groups`, `constraint`, `xml`, `inherit`, `upgrade` | Inherited view cannot have 'Groups' define on the record constraint error during module upgrade |
| 13 | [portal-dynamic-ui-mixed-data-odoo19.md](views/portal-dynamic-ui-mixed-data-odoo19.md) | 🟢 Low | 17, 18, 19 | `qweb`, `portal`, `ui`, `caching`, `mixed-targets` | Dynamic QWeb portal UI layout switching for mixed target models and bypassing browser cache |
| 14 | [portal-workflow-rule-viewer-bypass.md](views/portal-workflow-rule-viewer-bypass.md) | 🟡 Medium | 17, 18, 19 | `portal`, `controller`, `workflow`, `redirect`, `supervisor` | Prevent sequence enforcement rules from blocking supervisors reviewing visits |


### Security

| # | File | Severity | Versions | Tags | Description |
|---|------|----------|----------|------|-------------|
| 1 | [public-user-inactive-res-currency-accesserror.md](security/public-user-inactive-res-currency-accesserror.md) | 🔴 Critical | All | `security`, `access-rights`, `public-user`, `res.currency` | Public User deactivation or group loss causes AccessError during frontend QWeb rendering of res.currency |
| 2 | [stock-barcode-button-security-group.md](security/stock-barcode-button-security-group.md) | 🟢 Low | 17, 18, 19 | `security`, `owl`, `stock_barcode` | Adding Security Group Access Rights to Stock Barcode OWL Buttons by extending StockBarcodeController |
| 3 | [dynamic-portal-section-visibility.md](security/dynamic-portal-section-visibility.md) | 🟡 Medium | 16, 17, 18, 19 | `portal`, `security`, `dynamic-visibility`, `groups` | Dynamic portal section visibility via security groups instead of hardcoded strings or implied_ids |


### Performance

| # | File | Severity | Versions | Tags | Description |
|---|------|----------|----------|------|--------------|
| 1 | [n-plus-one-queries-computed-fields.md](performance/n-plus-one-queries-computed-fields.md) | 🔴 Critical | All | `performance`, `N+1`, `computed-fields`, `read_group`, `search` | Using `search()` inside computed field loops causes N+1 SQL queries — use `read_group()` instead |

### Deployment

_No entries yet._

### Upgrade

| # | File | Severity | Versions | Tags | Description |
|---|------|----------|----------|------|-------------|
| 1 | [analytic-distribution-migration-odoo18.md](upgrade/analytic-distribution-migration-odoo18.md) | 🔴 Critical | 18, 19 | `upgrade`, `migration`, `account.move.line`, `analytic_distribution` | account.move.line analytic_account_id field removal and migration to analytic_distribution in Odoo 18 |
| 2 | [qweb-report-invoice-reconciled-payments-odoo18.md](upgrade/qweb-report-invoice-reconciled-payments-odoo18.md) | 🔴 Critical | 17, 18, 19 | `upgrade`, `migration`, `account.move`, `qweb`, `report` | account.move _get_reconciled_info_JSON_values removal and migration to invoice_payments_widget in Odoo 18 |
| 3 | [crm-lead-mobile-field-removal.md](upgrade/crm-lead-mobile-field-removal.md) | 🔴 Critical | 19 | `upgrade`, `migration`, `crm.lead`, `mobile`, `field` | crm.lead mobile field removal in Odoo 19 causes AttributeError on access |
| 4 | [ir-sequence-company-dependent-deprecation.md](upgrade/ir-sequence-company-dependent-deprecation.md) | 🔴 Critical | 17, 18, 19 | `upgrade`, `migration`, `ir.sequence`, `company_dependent` | Invalid field 'company_dependent' on model 'ir.sequence' during module upgrade from Odoo 16 |

### Misc

| # | File | Severity | Versions | Tags | Description |
|---|------|----------|----------|------|-------------|
| 1 | [api_logging_decorator.md](misc/api_logging_decorator.md) | 🟢 Low | 16, 17, 18, 19 | `api`, `logging`, `decorator`, `security` | Log all API requests and JSON payloads using a custom decorator |
| 2 | [automated-xlsx-email-cron.md](misc/automated-xlsx-email-cron.md) | 🟡 Medium | 17, 18 | `xlsx`, `cron`, `email`, `report`, `pos`, `scheduled-action` | Automated XLSX report email via Cron with configurable ir.config_parameter filters |
| 3 | [translation-newlines-issue.md](misc/translation-newlines-issue.md) | 🟡 Medium | 15, 16, 17, 18, 19 | `translation`, `i18n`, `po`, `newlines` | Translation fails for UserError when Python string contains explicit newlines (\n\n) |
| 4 | [po-file-syntax-fatal-errors.md](misc/po-file-syntax-fatal-errors.md) | 🔴 Critical | All | `translation`, `i18n`, `po`, `syntax`, `msgfmt`, `quotes` | Unescaped quotes or duplicate msgids in PO files crash the parser, preventing translations from loading |
| 5 | [translation-wiped-out-by-export.md](misc/translation-wiped-out-by-export.md) | 🔴 Critical | All | `translation`, `i18n`, `po`, `export`, `polib` | Odoo i18n export wipes out existing PO translations if they are missing in DB; securely restore via polib |

---

## 🔧 Quick Reference

### Files in This Repo

```
odoo-knowledge/
├── README.md              ← You are here (Index)
├── CONTRIBUTING.md         ← How to add/update entries
├── TEMPLATE.md             ← Template for new entries
├── setup/                  ← 13 entries
├── orm/                    ← 13 entries
├── views/                  ← 10 entries
├── security/               ← 2 entries
├── performance/            ← (empty)
├── deployment/             ← (empty)
├── upgrade/                ← 2 entries
└── misc/                   ← (empty)
```

### Stats

- **Total Entries:** 34
- **Last Updated:** 2026-06-06
- **Contributors:** ENG/Mohamed Saber, ENG/Mohamed Hamdy, ENG/Gamal Mansour

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding new entries.

**TL;DR:**
1. Copy `TEMPLATE.md` into the right category folder
2. Fill in all fields (especially Tags and Versions)
3. Update this `README.md` index table
4. Commit and push
| Frontend | [OWL Form View Crash on Kanban Navigation](frontend/owl-kanban-form-crash-invisible-fields.md) | V16, V17, V18, V19 |
| [Dynamic Phases (CRM Spirit)](orm/dynamic-phases-crm-spirit.md) | ORM | How to migrate from Selection to a dynamic phase model |
