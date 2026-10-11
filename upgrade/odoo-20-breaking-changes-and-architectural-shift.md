# Odoo 20 Architectural Shifts and Breaking Changes Guide

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 20                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-26                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo20`, `upgrade`, `breaking-changes`, `mail`, `tracking`, `account`, `parent-accounts`, `hr-payroll`, `work-entries`, `mrp`, `ai`, `mcp`

---

## Overview

Odoo 20 (September 2026 release) introduces major architectural and structural overhauls across technical frameworks, business modules (Accounting, MRP, Inventory, HR/Payroll), and AI integration. Custom modules and migrations from v18/v19 must accommodate several breaking changes and paradigm shifts.

---

## 1. Technical & Framework Breaking Changes

### A. Mail: In-Body Tracking (`mail.tracking.value` Removed)
- **What Changed:** Persistent tracking values (`mail.tracking.value` table entries) have been removed from standard storage. Tracking messages are now generated dynamically on the fly within the message body.
- **Impact on Custom Modules:** Any custom code querying `self.env['mail.tracking.value']` for field change history, audit logs, or metrics will fail or return empty datasets. Features like burndown charts and stage duration now compute from message contents or dedicated tracking endpoints.
- **Solution:** 
  - For custom modules relying on field change history, refactor to listen to `write()` overrides or inspect formatted message subtypes.
  - A compatibility module is provided by Odoo for legacy environments needing stored tracking records.

### B. Push Notifications: Firebase Deprecation
- **What Changed:** Firebase Cloud Messaging (FCM) is completely removed for web/mobile push notifications.
- **Solution:** Replaced with Odoo's internal proprietary push server. Custom modules hooking into FCM endpoints or credentials in `res.config.settings` must be migrated to Odoo's in-house push notification protocol.

### C. Source of Postings in `mail.mail`
- `mail.mail` now mandates/includes the source origin of each posting to enhance system-wide audit trails.

---

## 2. Accounting & Finance Shifts

### A. Parent Accounts Replace Account Groups (`account.group` Deprecated)
- **What Changed:** Account hierarchy is now structured using Parent Accounts (`parent_id` directly on `account.account`), completely replacing `account.group`.
- **Breaking Detail:** Account codes (`code`) are now **optional**.
- **Solution:** Update any XML data or Python logic referencing `group_id` on `account.account` to use `parent_id`. Do not assume `account.code` is always non-null.

### B. Asset Models Replaced by Depreciation Models
- **What Changed:** `account.asset.model` has been replaced by `depreciation models`. Automation and configuration behaviors are directly tied to the asset accounts themselves.

### C. Payment Status Lifecycle Renaming
- `In Process` -> `Paid`
- `Paid` -> `Reconciled`
- The manual "Mark as Reconciled" button has moved to the `Action` menu to encourage bank synchronization.

### D. Employee Expenses Menu Consolidated
- The standalone "Employee Expenses" menu in Accounting is removed. Approved expense sheets now generate draft bills directly in the default purchase/expense journal.

### E. Fiscal Position Tax Removal
- If a default product/account tax is not present in the customer's Fiscal Position, it is automatically stripped even if no replacement rule is specified.

---

## 3. HR & Payroll Overhaul

### A. Complete Removal of Work Entries (`hr.work.entry`)
- **What Changed:** `hr.work.entry` and the Planning-Payroll bridge have been eliminated.
- **Unification:** Work entry types and Time Off types are now merged into a unified model.
- **Impact:** Custom modules overriding `_generate_work_entries` or querying work entries must migrate directly to time off / attendance schedule computations.

### B. Strict Contract Date Integrity
- Changing employee contract dates is strictly blocked if existing payslips overlap. Payslips must be explicitly canceled/reverted first.

---

## 4. MRP & Inventory

### A. BoM Flexible Consumption Deprecation
- The `flexible_consumption` field on `mrp.bom` has been removed. All Manufacturing Orders now operate with flexible consumption enabled by default.

### B. Produce Button Consolidation
- "Produce" and "Produce All" buttons are merged into a single "Produce" action across MRP, Shop Floor, and Barcode apps.

### C. Inventory Return Wizard Removed
- The multi-step return wizard is removed in favor of a direct, simplified 1-click return operation.

### D. Retroactive COGS & Landed Costs
- Changes in delivered product costs (e.g. late landed costs or vendor bill price variances) now retroactively update stock moves and COGS accounting entries under perpetual valuation.

---

## 5. Sales & CRM

### A. Description-Only Sales Order Lines
- `product_id` is no longer mandatory on `sale.order.line`. Lines can be created purely with a description unless the "Mandatory Product" configuration is toggled.

### B. Payment-Based Commissions
- Native sales commission engine supports calculation triggered upon actual invoice payment rather than invoice validation.

---

## 6. AI & Agentic Ecosystem

### A. Model Context Protocol (MCP) Support
- Odoo 20 natively exposes database resources and tools via MCP, enabling direct connection with external agentic systems and local IDE tools.

### B. AI Agents & Automated Actions
- AI agents can be invoked by Automated Actions (`base.automation`) and Scheduled Actions (`ir.cron`).
- AI "Topics" are renamed to "Skills".
- Tool calls enforce confirmation limits and interactive prompt approvals via UI buttons.
