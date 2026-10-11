# Multi-Company Demo Data Isolation Trap: Stranded Records Hide Custom Screens

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `multi-company`, `demo-data`, `ir.rule`, `empty-screens`, `pre-sales`, `company_ids`, `data-isolation`

---

## Problem

During enterprise client demos or QA walkthroughs, entire departments and menu trees (e.g., HSE Risk Assessments, Method Statements, Training Sessions, PPE Issuances, QA/QC ITPs, Equipment, Bank Guarantees) appear completely **EMPTY** (0 records) to the administrator, even though developers ran demo/seed scripts without errors.

The UI displays blank list views:
```
No records found. Create one?
```
Yet running SQL or ORM count without environment company filters shows records do exist in the database.

## Root Cause

1. **Company Mismatch in Multi-Company Deployments:** Standard Odoo demo data (or boilerplate demo XML files) frequently reference `base.main_company_chicago` (`company_id = 2`) for secondary records, while the primary enterprise projects, contracts, employees, and the admin user's active session are scoped to `base.main_company` (`company_id = 1`).
2. **Silent `ir.rule` Filtering:** All custom models with multi-company rules enforce `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`. When the user is logged into Company 1, any record with `company_id = 2` is completely invisible in the web client, creating the false appearance of an unfinished or empty module.
3. **Foreign Key Parent-Child Company Divergence:** Child operational records (e.g. a Risk Assessment or Method Statement) were assigned `company_id = 2` while their foreign key parent `project_id` belonged to Company 1.

## Solution ✅

### 1. Detect Company 1 vs Company 2 Stranded Records
Run an automated audit across all tables to locate models where records are isolated in Company 2:

```python
# Check tables where company_id = 2 while projects are in company_id = 1
cur.execute("""
    SELECT table_name 
    FROM information_schema.columns 
    WHERE column_name = 'company_id' AND table_schema = 'public'
""")
# Identify stranded counts per table
```

### 2. Batch Harmonize Demo Company IDs
Align all custom operational records to match the primary enterprise demo company (Company 1):

```sql
UPDATE hse_risk_assessment SET company_id = 1 WHERE company_id = 2;
UPDATE hse_method_statement SET company_id = 1 WHERE company_id = 2;
UPDATE hse_training_session SET company_id = 1 WHERE company_id = 2;
UPDATE hse_ppe_issuance SET company_id = 1 WHERE company_id = 2;
UPDATE qc_itp SET company_id = 1 WHERE company_id = 2;
UPDATE qc_snag_list SET company_id = 1 WHERE company_id = 2;
UPDATE construction_equipment SET company_id = 1 WHERE company_id = 2;
UPDATE dlp_warranty SET company_id = 1 WHERE company_id = 2;
UPDATE construction_bank_guarantee SET company_id = 1 WHERE company_id = 2;
```

### 3. Seed Primary Project Links
Ensure that the flagship project (`construction.project` ID 108) has dedicated records with valid selection fields:
- `hse.observation.obs_type`: use `'safe_act'`, `'unsafe_act'`, `'unsafe_condition'` (not `'safe'`).
- `hse.method.statement`: status is tracked via `ms_state` or `approval_status` (not bare `state`).
- `hse.ppe.issuance.line`: requires configured `hse.ppe.type` records with `category`.

## ⚠️ Pitfalls

- **Do NOT set `company_id` to a secondary company in demo XML without adding that company to the demo user's active session:** If a module ships demo data for Company 2, the user must either have both companies selected in the top bar or all records should default to `company_id = 1`.
- **Global Data vs Company-Specific:** If a catalog is meant to be shared across all branches (e.g., `hse.ppe.type` or `construction.cost.code`), set `company_id = False` or omit multi-company restrictions.

## Verification

Run an ORM query scoped to the user's active company:
```python
count = env['hse.risk.assessment'].search_count(['|', ('company_id', '=', 1), ('company_id', '=', False)])
assert count > 0, "Screen will appear empty in Company 1!"
```
