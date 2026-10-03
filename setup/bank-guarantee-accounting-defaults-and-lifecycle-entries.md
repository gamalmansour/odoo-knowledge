# Bank Guarantee Accounting Defaults & Lifecycle Journal Entries

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `bank-guarantees`, `letters-of-guarantee`, `accounting`, `res.company`, `res.config.settings`, `demo-data`

---

## Problem

Under **Settings > Construction Finance**, the **Bank Guarantees (خطابات الضمان)** configuration section displays empty fields:
- Cash Margin Account (`lg_margin_account_id`): Empty
- Commission Expense Account (`lg_commission_expense_account_id`): Empty
- LG Journal (`lg_journal_id`): Empty
- Forfeiture Account (`lg_forfeit_account_id`): Empty

When a user attempts to activate an issued letter of guarantee that has a cash margin or commission fee, the action crashes with:

```
odoo.exceptions.UserError: Please configure the LG Journal in the Settings.
```
or
```
odoo.exceptions.UserError: Please configure the LG Cash Margin Account in the Settings.
```

Similarly, attempting to forfeit or release the guarantee raises configuration errors.

---

## Root Cause

1. **Company Accounts Bound in Manifest Demo Files Only:**
   The initial XML records binding `lg_margin_account_id`, `lg_commission_expense_account_id`, `lg_journal_id`, and `lg_forfeit_account_id` to `res.company` were loaded via `data/demo_company_config.xml` under the `'demo': [...]` array of `__manifest__.py`.
2. **Chart-of-Accounts Demo Accounts Dependency:**
   The accounts themselves (`acc_lg_margin`, `acc_lg_commission`, `acc_lg_forfeit`, `journal_lg`) were defined in `construction_contract/demo/demo_accounts.xml` and `demo_journals.xml`, also only in demo data.
3. In any environment initialized or upgraded without demo data (`--without-demo` or standard clean deployment), `res.company` fields evaluate to `False`, rendering all letter of guarantee lifecycle buttons deadlocked.

---

## Solution ✅

### 1. Programmatic Idempotent Defaults in `res.company`

Implement an automated helper on `res.company` that provisions or locates the dedicated accounts and general journal, and binds them:

```python
def _ensure_construction_finance_defaults(self) -> None:
    for company in self:
        Account = self.env['account.account'].with_company(company)
        Journal = self.env['account.journal'].with_company(company)

        # 1. Margin Account (Current Asset)
        if not company.lg_margin_account_id:
            acc = Account.search([('code', '=', '102030'), ('company_ids', 'in', [company.id])], limit=1)
            if not acc:
                acc = Account.create({
                    'code': '102030',
                    'name': 'الغطاء النقدي لخطابات الضمان (هوامش محتجزة)',
                    'account_type': 'asset_current',
                    'company_ids': [(6, 0, [company.id])],
                })
            company.lg_margin_account_id = acc.id

        # 2. Commission Expense (Expense)
        if not company.lg_commission_expense_account_id:
            acc = Account.search([('code', '=', '400080'), ('company_ids', 'in', [company.id])], limit=1)
            if not acc:
                acc = Account.create({
                    'code': '400080',
                    'name': 'مصاريف وعمولات إصدار وتجديد خطابات الضمان',
                    'account_type': 'expense',
                    'company_ids': [(6, 0, [company.id])],
                })
            company.lg_commission_expense_account_id = acc.id

        # 3. LG General Journal
        if not company.lg_journal_id:
            jnl = Journal.search([('code', '=', 'LG'), ('company_id', '=', company.id)], limit=1)
            if not jnl:
                jnl = Journal.create({
                    'name': 'دفتر خطابات الضمان البنكية',
                    'code': 'LG',
                    'type': 'general',
                    'company_id': company.id,
                })
            company.lg_journal_id = jnl.id

        # 4. Forfeiture Loss Account (Expense)
        if not company.lg_forfeit_account_id:
            acc = Account.search([('code', '=', '400081'), ('company_ids', 'in', [company.id])], limit=1)
            if not acc:
                acc = Account.create({
                    'code': '400081',
                    'name': 'خسائر مصادرة وتسييل خطابات الضمان',
                    'account_type': 'expense',
                    'company_ids': [(6, 0, [company.id])],
                })
            company.lg_forfeit_account_id = acc.id
```

### 2. Auto-Trigger in `post_init_hook` & Settings Wizard

- Hook `post_init_hook` in `__manifest__.py`:
  ```python
  'post_init_hook': 'post_init_hook',
  ```
  ```python
  def post_init_hook(env):
      for company in env['res.company'].search([]):
          company._ensure_construction_finance_defaults()
  ```
- Add an interactive button in `res.config.settings` for administrators to re-sync defaults at will.

### 3. Balanced Accounting Entries Flow

- **Activation (`action_activate`):**
  - Dr: `102030` Cash Margin (Asset) [Partner = Bank]
  - Dr: `400080` Commission Expense (Expense) [Analytic Distribution = Project]
  - Cr: Payment Journal Bank Account (Asset)
- **Release (`action_release`):**
  - Dr: Payment Journal Bank Account (Asset)
  - Cr: `102030` Cash Margin (Asset) [Partner = Bank]
  *(Commission remains non-refundable as designed)*
- **Forfeiture (`action_forfeit`):**
  - Dr: `400081` LG Forfeiture (Expense)
  - Cr: `102030` Cash Margin (Asset) / Bank Account

---

## ⚠️ Pitfalls

1. **Odoo 18 Multi-Company on `account.account`:** Always use `company_ids` (Many2many) with `[(6, 0, [company.id])]` or `.with_company(company)`. Using `company_id` will trigger `ValueError: Invalid field account.account.company_id`.
2. **Missing `payment_journal_id` on Guarantee:** If the user leaves the payment journal empty, activating will fail. Enforce or default `payment_journal_id` to the company's primary bank journal.
3. **Analytic Distribution Type:** Ensure `analytic_distribution` dictionary keys are strings (e.g. `{str(analytic_acc.id): 100.0}`) for Odoo 17 and 18.

---

## Verification

1. Inspect settings via shell:
   ```python
   settings = env['res.config.settings'].create({})
   assert settings.lg_margin_account_id.code == '102030'
   assert settings.lg_commission_expense_account_id.code == '400080'
   assert settings.lg_journal_id.code == 'LG'
   assert settings.lg_forfeit_account_id.code == '400081'
   ```
2. Activate a Bank Guarantee with margin and commission: verify `issue_move_id` is created, balanced, and posted in journal `LG`.
3. Release the guarantee: verify `release_move_id` returns the margin to the bank account and clears the margin account.
