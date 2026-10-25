# Commercial White-Label Addon Architecture vs. Client Demo Database Decoupling

| Field | Value |
|-------|-------|
| **Category** | Best Practices |
| **Odoo Versions** | All (16.0, 17.0, 18.0, 19.0, 20.0) |
| **Severity** | 🔴 Critical |
| **Modules** | `custom_addons/*` (All Commercial & Multi-Client Product Suites) |
| **Tags** | `architecture`, `white-label`, `commercial-addon`, `decoupling`, `naming-conventions`, `demo-data`, `rfp`, `ir_model_data`, `refactoring` |
| **Author** | ENG/Gamal Mansour |
| **Date Added** | 2026-10-25 |
| **Last Verified** | 2026-10-25 |

---

## Problem 🔴

When building or extending a **commercial, reusable, multi-client product suite** (e.g., `the_secret_hr_*`, `the_secret_realestate_*`, `the_secret_construction_*`) while simultaneously preparing a pre-sales proof-of-concept (PoC) or answering an RFP for a specific prospective client (e.g., "Al Ahly Tamkeen" or their third-party ERP vendor "SB Tech"), a critical architectural violation occurs if **client-specific or vendor-specific names leak into the addon source code (`custom_addons/`)**.

Examples of how this contamination happens:
- Naming files after the client or their external vendor: `controllers/sb_tech_webhook.py`, `models/tamkeen_kpi.py`, `report/tamkeen_reports.xml`.
- Naming Python classes, fields, or selection keys after the client/vendor: `TamkeenHrWebhookController`, `sb_tech_tx_id`, `tamkeen_branch_code`.
- Naming XML IDs, menus, actions, or salary rules with the client's name: `rule_tamkeen_microfinance_incentive`, `menu_tamkeen_operations`.
- Hardcoding the client's company name in QWeb report headers (`<span>شركة الأهلي تمكين للتمويل المتناهي الصغر</span>`) instead of binding dynamically to `doc.company_id.name`.
- Hardcoding client/vendor names in REST API routes (`/api/v1/sb-tech/hr-summary`) or HTTP signature headers (`X-SB-Tech-Signature`).

**Why this is a critical failure:**
1. **Destroys Commercial Reusability:** You cannot sell, demo, or deploy an addon to Client B when its source code, database columns, API endpoints, XML IDs, and PDF reports carry Client A's brand name.
2. **Painful Database Migrations Later:** Once fields and XML IDs (`ir.model.data`) are installed in a database under client-specific names, renaming them later requires delicate `ALTER TABLE RENAME COLUMN` and `UPDATE ir_model_data` surgeries to avoid losing stored data or crashing view inheritance.
3. **Confuses Product Layer with Demo Data Layer:** The addon code (`custom_addons/`) is the **permanent commercial asset**, whereas the demo database and its seed script (`seed_<client>_demo.py`) are **ephemeral client presentation layers**.

---

## Root Cause 🔍

Reading a client's RFP or requirements document and translating its business terms *literally* into technical identifiers inside `custom_addons/` instead of translating them into **domain-driven, white-label enterprise abstractions** (e.g., translating "SB Tech GL Integration" into `sb_tech_webhook.py` instead of `erp_gl_webhook.py`, or "Al Ahly Tamkeen Microfinance Target" into `rule_tamkeen_incentive` instead of `rule_Collection_portfolio_incentive`).

---

## Solution ✅

### 1. Strict Two-Layer Separation (The Golden Rule)

| Layer | Location | Allowed Naming & Content | Forbidden Content |
|---|---|---|---|
| **Layer 1: Commercial Product Code** | `custom_addons/<brand>_*/` (`models/`, `controllers/`, `views/`, `data/`, `report/`, `security/`, `i18n/`, `tests/`) | 100% generic, domain-driven, white-label identifiers (`<brand>_*`, `erp_gl_*`, `external_tx_id`, `company_id.name`) | **ZERO** client names, **ZERO** third-party vendor names, **ZERO** client-specific Arabic/English labels in `.py`, `.xml`, `.csv`, `.po`, or `README.md` |
| **Layer 2: Client Demo / PoC Environment** | Standalone DB (`<client>_demo` or `<brand>_hr`) + external seed script (`scripts/seed_<client>_demo.py`) | Client company name in `res.company`, client branches in `hr.location`/`hr.department`, client job titles, realistic employee headcount & sample transactions | Never committed inside `custom_addons/` |

### 2. White-Label Naming Mapping Standards

When implementing a requirement from a client RFP into a commercial addon, always generalize the technical and UI naming:

```python
# ❌ WRONG — Client/Vendor name leaked into commercial addon code
class SbTechWebhookController(http.Controller):
    @http.route('/api/v1/sb-tech/hr-summary', type='http', auth='none', methods=['POST'], csrf=False)
    def push_tamkeen_gl_summary(self, **kwargs):
        signature = request.httprequest.headers.get('X-SB-Tech-Signature')
        ...

# ✅ CORRECT — 100% Generic White-Label Enterprise Architecture
class ErpGlWebhookController(http.Controller):
    @http.route('/api/v1/erp-gl/hr-summary', type='http', auth='none', methods=['POST'], csrf=False)
    def push_erp_gl_summary(self, **kwargs):
        signature = request.httprequest.headers.get('X-ERP-GL-Signature')
        ...
```

And in QWeb Reports (`report/*.xml`):
```xml
<!-- ❌ WRONG — Hardcoded client company name in QWeb template -->
<div class="text-muted">شركة الأهلي تمكين للتمويل المتناهي الصغر</div>

<!-- ✅ CORRECT — Dynamic company name from the record's company_id -->
<div class="text-muted"><span t-field="doc.company_id.name"/></div>
```

### 3. Safe In-Place Database Migration Recipe (If Refactoring an Already-Installed DB)

If a client-named XML ID, column, or rule code was accidentally installed on a live/demo database and you refactor the addon to generic names, execute this atomic SQL migration **before** running `-u <modules>` so Odoo updates existing records in-place instead of creating duplicates or failing on orphan XML IDs:

```sql
BEGIN;
-- 1. Remap XML IDs in ir_model_data so -u updates existing records in-place
UPDATE ir_model_data
SET name = REPLACE(name, 'tamkeen', 'enterprise')
WHERE module LIKE 'the_secret_%' AND name LIKE '%tamkeen%';

-- 2. Rename any database columns or config parameters if applicable
UPDATE ir_config_parameter
SET key = REPLACE(key, 'sb_tech', 'erp_gl')
WHERE key LIKE '%sb_tech%';
COMMIT;
```

### 4. Mandatory Zero-Contamination Audit Gate (Before Every Commit / Delivery)

Before considering any task on a commercial addon complete, run both verification commands against `custom_addons/` (note the trailing slash if `custom_addons/` is a symlink):

```bash
# 1. Verify zero file or folder names contain client/vendor keywords
find -L custom_addons/ -iname "*<client_keyword>*" -o -iname "*<vendor_keyword>*"

# 2. Verify zero occurrences inside any code, XML, PO, or test file
grep -rnI -i -E "<client_keyword_en>|<vendor_keyword_en>|<client_keyword_ar>" custom_addons/
```
Both commands **MUST return `0` matches**.

---

## ⚠️ Pitfalls

- **Symlink Traversal in `find` and `grep`:** If `custom_addons` is a symlink pointing to another directory, running `find custom_addons` without `-L` or without a trailing slash `custom_addons/` will only inspect the symlink file itself and return `0` even if polluted files exist inside. Always use `find -L custom_addons/` and `grep -rnI ... custom_addons/`.
- **Forgotten `.pyc` Bytecode Cache:** After renaming a Python file (e.g., `sb_tech_webhook.py` → `erp_gl_webhook.py`), always clean `__pycache__/*.pyc` so stale bytecode does not linger on disk.
- **Forgotten `i18n/ar.po` & `tests/`:** Even if models and views are clean, developers often leave client names inside test docstrings (`test_tamkeen_incentive`) or `.po` comments/translations. The `grep -rnI` gate must scan the entire module tree including `tests/`, `i18n/`, and `README.md`.

---

## Related Entries

- [Odoo Apps Store (`apps.odoo.com`) HTML Sanitizer & Standalone Module Decoupling](odoo-apps-store-publishing-sanitizer-and-decoupling.md)
- [Multi-Market Construction Localization and Demo Decoupling](multi-market-construction-localization-and-demo-decoupling.md)
