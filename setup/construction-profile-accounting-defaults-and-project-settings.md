# Construction Profile Accounting Defaults & Project Costing Settings

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `construction`, `construction_profile`, `accounting`, `wip`, `costing`, `revenue_recognition`, `journals`, `chart_of_accounts`, `odoo18`

---

## Problem

When inspecting or creating construction profiles (`construction.profile` via `construction_contract.view_construction_profile_form`), the **"Project Settings"** and **"Contract Defaults"** tabs show completely blank accounting fields:

1. In **Project Settings**:
   - `journal_construction_cost_id` is empty.
   - `account_wip_id` is empty.
   - `account_labor_cost_id`, `account_equipment_cost_id`, `account_material_cost_id` are empty.
   - `journal_recognition_id`, `account_revenue_id`, `account_wip_revenue_id` are empty.
2. In **Contract Defaults**:
   - `account_equipment_hire_id`, `account_advance_id`, `account_retention_id`, `account_advance_sub_id`, `account_retention_sub_id` are empty.

When a project executes work orders, attempts WIP cost posting, or generates subcontractor IPC progress billings, the transaction fails with missing account configuration errors.

---

## Root Cause

`construction_contract/data/construction_profile_data.xml` defines default operational profiles (`Residential`, `Infrastructure`, `Industrial`) with markup percentages (`overhead_percentage`, `profit_margin_percentage`, `advance_percentage`, `retention_percentage`), but deliberately omits accounting accounts. 

Because Odoo's Chart of Accounts (COA) is company- and localization-dependent (`l10n_eg`, `l10n_sa`, `generic_coa`), hardcoding account XML IDs in module data files either crashes installation when those accounts do not exist, or leaves fields empty.

---

## Solution ✅

Configure dedicated construction journals and standard chart of accounts per company, then populate them across all construction profiles.

### 1. Create Dedicated Journals
- `CCJ`: دفتر تكاليف المشروعات الإنشائية (Construction Cost Journal, type: `general`)
- `RRJ`: دفتر إثبات الإيرادات والمستخلصات (Revenue Recognition Journal, type: `general`)

### 2. Standard Chart of Accounts Mapping (IFRS / Egyptian Accounting Standards)
- **WIP / Cost Clearing**: `107001` - أعمال ومشروعات تحت التنفيذ (WIP - Construction in Progress) [`asset_current`]
- **Unbilled Revenue**: `107002` - إيرادات عقود غير مفوترة - أصول عقود (Unbilled Contract Revenue - IFRS 15) [`asset_current`]
- **Retention Receivable**: `107003` - محتجزات تأمين أعمال طرف العملاء (Retention Receivable) [`asset_current`]
- **Subcontractor Advances**: `107004` - دفعات مقدمة لمقاولي الباطن (Subcontractor Advances) [`asset_current`]
- **Materials on Site (FIDIC 14.5)**: `107005` - تشوينات ومواد بالموقع (Materials On Site) [`asset_current`]
- **Customer Advances**: `205001` - دفعات مقدمة من عملاء المشروعات (Customer Advances) [`liability_current`]
- **Subcontractor Retention**: `205002` - محتجزات تأمين أعمال لمقاولي الباطن (Subcontractor Retention Payable) [`liability_current`]
- **Direct Material Cost**: `400085` - تكاليف ومصروفات مواد المشروعات (Direct Material Cost) [`expense`]
- **Direct Labor Cost**: `400086` - تكاليف ومصروفات عمالة المشروعات المباشرة (Direct Labor Cost) [`expense`]
- **Direct Equipment Cost**: `400087` - تكاليف وتشغيل معدات المشروعات (Direct Equipment Cost) [`expense`]
- **Equipment Hire**: `400088` - تكاليف استئجار معدات وآليات من مقاولين (Equipment Hire) [`expense`]
- **Contract Revenue**: `500015` - إيرادات عقود المقاولات المعتمدة (Contract Revenue - IFRS 15) [`income`]
- **Price Escalation (FIDIC 13.8)**: `500016` - فروق أسعار وتعديل تكاليف (Price Escalation) [`income`]

### 3. Automated Configuration Script
```python
profiles = env['construction.profile'].search([])
profiles.write({
    'journal_construction_cost_id': cc_journal.id,
    'account_wip_id': acc_wip.id,
    'account_material_cost_id': acc_material.id,
    'account_labor_cost_id': acc_labor.id,
    'account_equipment_cost_id': acc_equipment.id,
    'journal_recognition_id': rr_journal.id,
    'account_revenue_id': acc_revenue.id,
    'account_wip_revenue_id': acc_wip_revenue.id,
    'account_equipment_hire_id': acc_equipment_hire.id,
    'account_advance_id': acc_advance.id,
    'account_retention_id': acc_retention.id,
    'account_advance_sub_id': acc_advance_sub.id,
    'account_retention_sub_id': acc_retention_sub.id,
    'account_escalation_id': acc_escalation.id,
    'account_mos_id': acc_mos.id,
})
```

---

## ⚠️ Pitfalls

1. **Domain Restrictions on Profile Fields**:
   - `account_labor_cost_id`, `account_equipment_cost_id`, `account_material_cost_id` enforce `[('account_type', '=', 'expense')]`. Setting them to `expense_direct_cost` in certain Odoo versions triggers a domain violation in the UI unless `account_type` matches `'expense'`.
   - `account_advance_id` and `account_retention_id` strictly disallow `asset_receivable` and `liability_payable` because Odoo's payment term reconciler swallows deduction lines on progress invoices, causing unexplained invoice imbalance.
2. **Project Inheritance**:
   When projects are created, ensure they are linked to a profile (`project.profile_id`), otherwise project-level defaulting falls back to empty values.

---

## Verification

In Odoo Shell:
```python
for p in env['construction.profile'].search([]):
    assert p.journal_construction_cost_id
    assert p.account_wip_id
    assert p.account_material_cost_id
    assert p.account_labor_cost_id
    assert p.account_equipment_cost_id
    assert p.journal_recognition_id
    assert p.account_revenue_id
    assert p.account_advance_id
    assert p.account_retention_id
```

---

## References

- Related: `setup/bank-guarantee-accounting-defaults-and-lifecycle-entries.md`
- Related: `orm/construction-p2p-requisition-po-grn-store-issue-accounting-flow.md`
