# Company Custody Accounting Config & Employee Partner Deadlock

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `custody`, `accounting`, `res.company`, `hr.employee`, `work_contact_id`, `deadlock`, `demo-data`

---

## Problem

Users navigate to **Custody Requests** and **Custody Reconciliations** in construction finance and find both screens completely empty. When creating a custody request manually and attempting to approve or pay it, the transaction crashes with:

```
odoo.exceptions.UserError: Please configure the Custody Account and Journal in the Settings.
```

Or, if an employee is selected without a linked contact partner:

```
odoo.exceptions.UserError: The custodian employee must have a linked Work Contact (Partner) or User to post accounting entries.
```

---

## Root Cause

1. **Company Accounting Defaults Stored Under Manifest `demo` Key:**
   The XML configuring `custody_account_id` and `custody_journal_id` on `res.company` was included under the `'demo': [...]` array in `__manifest__.py` instead of being handled reliably. When databases are installed or upgraded without demo data (e.g. standard production or pre-sales environments), `res.company` has `False` for both fields, rendering the entire module's action buttons deadlocked.

2. **Decoupled HR Employee & Partner Linkage (`work_contact_id`):**
   In Odoo 17 and 18, `hr.employee` is decoupled from `res.partner`. To post journal entries (`account.move.line`) tracking petty cash per custodian, the ORM requires a partner on the receivable/current asset line. If the employee lacks `work_contact_id` (or `user_id.partner_id`), journal creation aborts.

---

## Solution ✅

### 1. Ensure Default Custody Account & Journal Exist and Are Bound to Company

```python
company = env.company

# 1. Ensure asset account exists
Account = env['account.account'].with_company(company)
custody_account = company.custody_account_id
if not custody_account:
    custody_account = Account.search([('code', '=', '102020')], limit=1)
    if not custody_account:
        custody_account = Account.create({
            'code': '102020',
            'name': 'أرصدة العُهد النقدية للمشاريع والموظفين',
            'account_type': 'asset_current',
            'company_ids': [(6, 0, [company.id])],
        })
    company.custody_account_id = custody_account.id

# 2. Ensure general custody journal exists
Journal = env['account.journal'].with_company(company)
custody_journal = company.custody_journal_id
if not custody_journal:
    custody_journal = Journal.search([('code', '=', 'CUST'), ('company_id', '=', company.id)], limit=1)
    if not custody_journal:
        custody_journal = Journal.create({
            'name': 'دفتر قيود العُهد النقدية وتسوياتها',
            'code': 'CUST',
            'type': 'general',
            'company_id': company.id,
        })
    company.custody_journal_id = custody_journal.id
```

### 2. Guarantee Custodian Employees Have a Linked Work Contact Partner

```python
Partner = env['res.partner'].with_company(company)
if not employee.work_contact_id:
    partner = Partner.search([('name', '=', employee.name)], limit=1)
    if not partner:
        partner = Partner.create({
            'name': employee.name,
            'is_company': False,
            'company_id': company.id,
        })
    employee.work_contact_id = partner.id
```

### 3. Maintain Balanced End-to-End Accounting Lifecycle

- **Custody Advance (Pay):**
  - Dr: Custody Account (Asset) [Partner = Custodian]
  - Cr: Bank / Cash Account (Asset)
- **Custody Settlement (Post Reconcile):**
  - Dr: Project Cost Accounts (Expenses) [Analytic Distribution = Project]
  - Cr: Custody Account (Asset) [Partner = Custodian]
- **Return Leftover (Close):**
  - Dr: Bank / Cash Account (Asset)
  - Cr: Custody Account (Asset) [Partner = Custodian]

---

## ⚠️ Pitfalls

- **Do NOT place initial company configuration in demo data**: Place setup logic in data files or post_init_hooks.
- **Account Multi-Company in Odoo 18**: `account.account` uses `company_ids` (Many2many) in V18, not `company_id`. Always query using `.with_company(company)` or domain `[('company_ids', 'in', company.id)]`.
- **Server Action Dynamic Context**: When creating summary reports on `account.move.line` for custody balances, ensure the server action checks `company.custody_account_id` defensively and groups by `partner_id`.

---

## Verification

1. Check company settings:
   ```python
   assert env.company.custody_account_id and env.company.custody_journal_id
   ```
2. Verify Custody Requests and Reconciliations show active populated records across all lifecycle stages (`draft`, `submitted`, `approved`, `paid`, `posted`, `closed`).
3. Open `Custody Balance by Custodian` report: view renders pivot/list grouped by custodian partner with matching debit/credit residuals.
