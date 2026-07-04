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
| 15 | [clean-db-install-verification-demo-as-data-and-missing-rule-fields.md](setup/clean-db-install-verification-demo-as-data-and-missing-rule-fields.md) | 🔴 Critical | All | `install`, `verification`, `demo`, `ir.rule`, `clean-db`, `ci` | A clean-DB `-i --without-demo` install (+ a with-demo pass) catches install-blockers static review misses: demo records scattered under the `data` key (pollute prod + break cross-module refs) and `ir.rule` domains traversing to a non-existent model field |

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
| 19 | [testing-compute-fields.md](orm/testing_compute_fields.md) | 🟡 Medium | 16, 17, 18, 19 | `testing`, `orm`, `compute_fields`, `dates` | Resolves test assertions failing when manually updating date fields for testing compute behaviors due to state staleness |
| 20 | [testing-projects-contract-constraints.md](backend/testing-projects-contract-constraints.md) | 🔴 Critical | 17+ | `testing`, `orm`, `constraints` | Successfully mock `construction.project` and satisfy its raw SQL NOT NULL constraints for testing |
| 21 | [testing-access-error-base-group-user.md](backend/testing-access-error-base-group-user.md) | 🔴 Critical | All | `testing`, `security`, `groups` | Access errors during tests because mock users were overwritten without `base.group_user` |
| 22 | [demo_data_generation_constraints.md](backend/demo_data_generation_constraints.md) | 🔴 Critical | 17 | `demo`, `constraints`, `valueerror` | Python demo generation constraints and incorrect field names causing ValueError |
| 23 | [create-invoice-from-stock-picking.md](orm/create-invoice-from-stock-picking.md) | 🟢 Low | 17, 18, 19 | `orm`, `stock.picking`, `sale.order`, `account.move` | Trigger invoice creation for the related Sale Order directly from Stock Picking (Delivery Order) |
| 24 | [auto-validate-returns-transit-location.md](models/auto-validate-returns-transit-location.md) | 🟡 Medium | 15, 16, 17, 18, 19 | `orm`, `stock.picking`, `returns`, `transit-location` | Auto-create and validate return stock.picking to vehicle transit location for sales returns |
| 25 | [stored-compute-incomplete-depends-silent-staleness.md](orm/stored-compute-incomplete-depends-silent-staleness.md) | 🔴 Critical | All | `orm`, `computed-fields`, `store`, `api.depends`, `staleness`, `kpi`, `roi` | Stored compute whose `@api.depends` omits the real upstream data freezes at first value — KPI/ROI/money figures go silently stale, "Refresh" button does nothing |
| 26 | [money-flow-reversal-on-refund-cancel-reset-draft.md](orm/money-flow-reversal-on-refund-cancel-reset-draft.md) | 🔴 Critical | All | `orm`, `account`, `commission`, `out_refund`, `reversal`, `idempotency` | Commission/settlement records must reverse on refund, cancel, and reset-to-draft; ignoring `out_refund` and skipping `button_draft`/`button_cancel` causes directional, ever-growing over-payment |
| 27 | [idempotent-create-unique-constraint-savepoint.md](orm/idempotent-create-unique-constraint-savepoint.md) | 🔴 Critical | All | `orm`, `constraints`, `unique`, `savepoint`, `IntegrityError`, `idempotency` | A "load-or-create" flow collides with a `unique(...)` SQL constraint because the uniqueness key came from a field default; allocate the next free key, key the idempotency search on the same tuple as the constraint, and wrap the create in `cr.savepoint()` to degrade gracefully |
| 28 | [resource-calendar-working-day-api-odoo19.md](orm/resource-calendar-working-day-api-odoo19.md) | 🔴 Critical | 19 | `orm`, `resource.calendar`, `attendance`, `working-day`, `odoo19`, `upgrade` | `resource.calendar._get_calendars_attendance_intervals` does not exist in Odoo 19 (AttributeError); use the supported `_works_on_date(date)` to test a working day, or `_attendance_intervals_batch` for ranges |
| 29 | [inconsistent-store-compute-sudo-computed-fields.md](orm/inconsistent-store-compute-sudo-computed-fields.md) | 🔴 Critical | 17, 18, 19 | `orm`, `computed-fields`, `store`, `compute_sudo`, `registry` | Inconsistent store or compute_sudo attributes on computed fields computed by the same method causes Odoo to skip DB column creation |
| 30 | [override-compute-narrowed-depends-freezes-parent-stored-fields.md](orm/override-compute-narrowed-depends-freezes-parent-stored-fields.md) | 🔴 Critical | All | `orm`, `computed-fields`, `store`, `api.depends`, `inheritance`, `override`, `cross-module` | Overriding a stored compute in an inheriting module with a narrowed `@api.depends` replaces the parent's dependency list and silently freezes ALL the parent's stored fields once the second module is installed |
| 31 | [counting-fields-regex-digit-gotcha-and-safe-bulk-help.md](orm/counting-fields-regex-digit-gotcha-and-safe-bulk-help.md) | 🟡 Medium | All | `orm`, `fields`, `regex`, `audit`, `help`, `documentation`, `many2one`, `coverage` | Field-counting regex `fields\.[A-Z][a-zA-Z]*(` silently misses Many2one/One2many/Many2many (the digit 2 breaks `[a-zA-Z]*`) → ~33% undercount; plus a deterministically-verified workflow to bulk-add `help=` to every field |
| 32 | [translated_many2one_search.md](orm/translated_many2one_search.md) | 🔴 Critical | 16, 17, 18, 19 | `orm`, `name`, `translated`, `_rec_names_search`, `postgres`, `psycopg2` | Adding translate=True to core name fields breaks postgres schemas in search logic. Use _rec_names_search for alternate language names. |
| 33 | [one2many_import_boq.md](orm/one2many_import_boq.md) | 🟢 Low | 16, 17, 18, 19 | `orm`, `one2many`, `hierarchy`, `boq`, `import` | Pattern for importing hierarchical one2many data (like BOQ) via button instead of complex onchange |
| 34 | [side-register-must-move-stock-and-dedup-kpi.md](orm/side-register-must-move-stock-and-dedup-kpi.md) | 🔴 Critical | All | `orm`, `stock`, `stock.scrap`, `kpi`, `double-counting`, `anti-tamper` | Waste/loss/damage side-registers must physically scrap stock, take cost from valuation layers, lock after confirm, and dedup against wastage-classified issues to prevent phantom stock and KPI double counting |
| 35 | [receivable-payable-account-move-line-due-date-constraint.md](orm/receivable-payable-account-move-line-due-date-constraint.md) | 🔴 Critical | 16, 17, 18, 19 | `orm`, `account`, `constraint` | Missing display_type='payment_term' on receivable/payable account.move.line creation throws due date UserError |

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
| 15 | [owl-client-action-scrolling.md](frontend/owl-client-action-scrolling.md) | 🔴 Critical | 16, 17, 18, 19 | `owl`, `client-action`, `scrolling`, `o_content` | Vertical scrolling broken/clipped in custom OWL client actions due to missing o_content wrapper inside o_action |
| 16 | [portal-supervisor-subordinates-domain.md](views/portal-supervisor-subordinates-domain.md) | 🟡 Medium | All | `portal`, `domain`, `subordinates`, `supervisor` | Supervisor's portal doesn't show visits for their subordinates because the domain only checked the plan's supervisor ID |
| 17 | [owl-many2many-list-sum-crash.md](views/owl-many2many-list-sum-crash.md) | 🔴 Critical | 17, 18, 19 | `owl`, `views`, `many2many`, `sum`, `crash` | OWL ListRenderer crashes when using sum attribute on fields inside a Many2many list view |
| 18 | [scss-import-compilation-error.md](views/scss-import-compilation-error.md) | 🔴 Critical | All | `css`, `scss`, `import`, `assets` | Adding external CSS `@import` inside SCSS/CSS files breaks Odoo asset compilation |
| 19 | [invalid-action-window-target-inline.md](views/invalid-action-window-target-inline.md) | 🔴 Critical | 18, 19 | `views`, `res.config.settings`, `ir.actions.act_window`, `target`, `inline` | Invalid target='inline' value in act_window causing installation crash |
| 20 | [portal-cards-url-visibility-odoo19.md](views/portal-cards-url-visibility-odoo19.md) | 🟡 Medium | 19 | `portal`, `url`, `odoo19` | Hiding portal cards fails because Odoo 19 appends ?filterby query parameters to URLs |
| 21 | [xml_syntax_error_javascript_ampersand.md](views/xml_syntax_error_javascript_ampersand.md) | 🔴 Critical | All | `qweb`, `xml`, `javascript`, `syntax error` | XML ParseEntityRef error caused by using && or < in QWeb inline JavaScript |
| 22 | [odoo19_portal_card_xpath_class_change.md](views/odoo19_portal_card_xpath_class_change.md) | 🟡 Medium | 19 | `xpath`, `qweb`, `portal`, `hasclass`, `odoo19` | XPath hasclass() fails in Odoo 19 because class attributes in portal templates were changed to dynamic t-att-class |
| 23 | [external_id_not_found_parse_error.md](views/external_id_not_found_parse_error.md) | 🔴 Critical | All | `xml`, `parseerror`, `manifest`, `data-order`, `external-id` | External ID not found ValueError caused by incorrect XML file load order in __manifest__.py |
| 24 | [odoo_19_list_view_for_one2many.md](views/odoo_19_list_view_for_one2many.md) | 🔴 Critical | 17, 18, 19 | `views`, `xml`, `one2many`, `list`, `tree` | Using list instead of tree for One2many inline views in Odoo 19+ to avoid XML ParseError |

### Security

| # | File | Severity | Versions | Tags | Description |
|---|------|----------|----------|------|-------------|
| 1 | [public-user-inactive-res-currency-accesserror.md](security/public-user-inactive-res-currency-accesserror.md) | 🔴 Critical | All | `security`, `access-rights`, `public-user`, `res.currency` | Public User deactivation or group loss causes AccessError during frontend QWeb rendering of res.currency |
| 2 | [stock-barcode-button-security-group.md](security/stock-barcode-button-security-group.md) | 🟢 Low | 17, 18, 19 | `security`, `owl`, `stock_barcode` | Adding Security Group Access Rights to Stock Barcode OWL Buttons by extending StockBarcodeController |
| 3 | [dynamic-portal-section-visibility.md](security/dynamic-portal-section-visibility.md) | 🟡 Medium | 16, 17, 18, 19 | `portal`, `security`, `dynamic-visibility`, `groups` | Dynamic portal section visibility via security groups instead of hardcoded strings or implied_ids |
| 4 | [portal-controller-sudo-browse-bypasses-record-rules-idor.md](security/portal-controller-sudo-browse-bypasses-record-rules-idor.md) | 🔴 Critical | All | `security`, `portal`, `controller`, `sudo`, `ir.rule`, `idor` | Portal controller `.sudo().browse(id)` disables record rules; a weak manual ownership check lets any user reach others' records by URL id enumeration (IDOR) |
| 5 | [sod-approval-checks.md](security/sod-approval-checks.md) | 🔴 Critical | All | `security`, `sod`, `approvals`, `workflow` | Implement Segregation of Duties (SoD) in custom approval engines to prevent users from approving their own records or multiple stages |
| 6 | [multi-company-record-rules.md](security/multi-company-record-rules.md) | 🔴 Critical | All | `security`, `multi-company`, `ir.rule`, `access-rights` | Custom models in a multi-company environment leak data across companies by default without explicit ir.rule |


### Performance

| # | File | Severity | Versions | Tags | Description |
|---|------|----------|----------|------|--------------|
| 1 | [n-plus-one-queries-computed-fields.md](performance/n-plus-one-queries-computed-fields.md) | 🔴 Critical | All | `performance`, `N+1`, `computed-fields`, `read_group`, `search` | Using `search()` inside computed field loops causes N+1 SQL queries — use `read_group()` instead |
| 2 | [sales-target-crm-won-customers-cartons.md](sale/sales-target-crm-won-customers-cartons.md) | 🟡 Medium | 16, 17, 18, 19 | `sale.target`, `crm.lead`, `uom`, `performance`, `n+1`, `read_group` | Efficiently compute product cartons and won crm customers in sales targets without N+1 query bottlenecks |
| 3 | [non-stored-compute-fields-in-list-and-search-views.md](performance/non-stored-compute-fields-in-list-and-search-views.md) | 🔴 Critical | All | `performance`, `computed-fields`, `store`, `list-view`, `search`, `scaling` | `store=False` computed fields placed in tree/search/group-by re-run the compute (often full table scans) on every render — instant in demo, multi-second after a year of data |
| 4 | [avoid-in-memory-record-filtering-in-wizards.md](performance/avoid-in-memory-record-filtering-in-wizards.md) | 🔴 Critical | All | `performance`, `memory-leak`, `filtered`, `orm`, `wizard` | Avoid loading entire database tables in memory when filtering by using native Odoo domains instead of Python's filtered(). |

### Deployment

_No entries yet._

### Upgrade

| # | File | Severity | Versions | Tags | Description |
|---|------|----------|----------|------|-------------|
| 1 | [analytic-distribution-migration-odoo18.md](upgrade/analytic-distribution-migration-odoo18.md) | 🔴 Critical | 18, 19 | `upgrade`, `migration`, `account.move.line`, `analytic_distribution` | account.move.line analytic_account_id field removal and migration to analytic_distribution in Odoo 18 |
| 2 | [qweb-report-invoice-reconciled-payments-odoo18.md](upgrade/qweb-report-invoice-reconciled-payments-odoo18.md) | 🔴 Critical | 17, 18, 19 | `upgrade`, `migration`, `account.move`, `qweb`, `report` | account.move _get_reconciled_info_JSON_values removal and migration to invoice_payments_widget in Odoo 18 |
| 3 | [crm-lead-mobile-field-removal.md](upgrade/crm-lead-mobile-field-removal.md) | 🔴 Critical | 19 | `upgrade`, `migration`, `crm.lead`, `mobile`, `field` | crm.lead mobile field removal in Odoo 19 causes AttributeError on access |
| 4 | [ir-sequence-company-dependent-deprecation.md](upgrade/ir-sequence-company-dependent-deprecation.md) | 🔴 Critical | 17, 18, 19 | `upgrade`, `migration`, `ir.sequence`, `company_dependent` | Invalid field 'company_dependent' on model 'ir.sequence' during module upgrade from Odoo 16 |
| 5 | [hr-employee-address-home-id-deprecation-odoo17.md](upgrade/hr-employee-address-home-id-deprecation-odoo17.md) | 🔴 Critical | 17, 18, 19 | `upgrade`, `hr.employee`, `address_home_id`, `work_contact_id` | ValueError for address_home_id on hr.employee because field was replaced by work_contact_id |
| 6 | [foreign-key-violation-ondelete-restrict.md](upgrade/foreign-key-violation-ondelete-restrict.md) | 🔴 Critical | 15, 16, 17, 18, 19 | `upgrade`, `foreign-key`, `ondelete`, `psycopg2` | Foreign Key Violation During Module Upgrade due to ondelete=x27restrictx27 |

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
├── orm/                    ← 14 entries
├── views/                  ← 10 entries
├── security/               ← 6 entries
├── performance/            ← (empty)
├── deployment/             ← (empty)
├── upgrade/                ← 2 entries
└── misc/                   ← (empty)
```

### Stats

- **Total Entries:** 37
- **Last Updated:** 2026-07-04
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
| Views | [Domain Date Restriction Pitfall](views/domain-date-restriction-pitfall.md) | Domain too strict for future scheduling |
| Models | [Delivery Order Destination Pitfall](models/delivery-order-destination-pitfall.md) | Prevent delivery orders from getting stuck in vehicle locations |
| Changing Search Fields in Target Models | changing_search_fields.md |
| `name_get_deprecation_odoo17.md` | upgrade | Deprecation of name_get in Odoo 17+ (Use _compute_display_name) |
| Data Migration | Complex Hierarchical Excel Import | [Link](data_migration/complex-hierarchical-excel-import.md) |
| Frontend | [POS JS Missing RPCError Import](frontend/pos_js_missing_rpcerror_import.md) | V18 |
