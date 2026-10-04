# POS Default Receivable Misconfiguration Hanging POS Accounts Receivable and Corrupting Tax Lines

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `pos`, `accounting`, `receivable`, `reconciliation`, `zatca`, `point_of_sale`

---

## Problem

When closing Point of Sale (POS) sessions with card payment methods (e.g. Mada, Visa):
1. The automated combine payment entry (`account.payment` / `account.move`) has its credit line mapped to the wrong account (e.g., VAT Receivable `100103` instead of POS Accounts Receivable `102012`).
2. Draft payment moves remain unposted because users hesitate to post entries crediting VAT.
3. The POS Accounts Receivable account (`102012`) accumulates massive open debit balances that cannot be automatically reconciled against session closings.
4. Cash difference / adjustment attempts result in inverted credit balances in loss accounts (`999002`).

---

## Root Cause

In Odoo POS (`addons/point_of_sale/models/pos_session.py`), `_create_combine_account_payment()` resolves the destination receivable account using:
```python
destination_account = payment_method.receivable_account_id or self.company_id.account_default_pos_receivable_account_id
```
If the chart of accounts setup or company configuration mistakenly assigns `account_default_pos_receivable_account_id` to a tax or suspense account (e.g. `100103`), all generated card payment entries credit that wrong account instead of `102012`.

---

## Solution ✅

### 1. Fix Root Company Setting
Ensure `res.company.account_default_pos_receivable_account_id` points to the designated POS Receivable account (`102012`):
```python
company = env.company
pos_receivable = env['account.account'].search([('code', '=', '102012')], limit=1)
company.account_default_pos_receivable_account_id = pos_receivable
```

### 2. Fix Existing Draft Payment Entries
For any draft combine payment entries:
1. Update the credit line account from `100103` to `102012`.
2. Update the debit line account to the real operating bank account (e.g., `130201001`).
3. Post the entry.

### 3. Clear Historical Misallocated Adjustment Entries
If manual adjustment entries credited cash difference accounts (e.g., `999002`) instead of `102012`:
Post an offsetting adjustment entry in Miscellaneous Operations:
- **Debit:** `[999002] Cash Difference Loss` (clears the abnormal credit).
- **Credit:** `[102012] Accounts Receivable (PoS)` (clears the remaining hanging debit).

---

## ⚠️ Pitfalls

- **Do NOT reset historical reconciled moves to draft:** Resetting moves whose debit lines are already reconciled in clearing accounts (`101003`) breaks the entire reconciliation batch. Always use an adjustment entry instead.
- **Ensure Reconcile is enabled on 102012:** The account must have `reconcile=True` to allow matching between session debits and payment credits.

---

## Verification

Check the posted balance of `102012`:
```sql
SELECT SUM(balance) FROM account_move_line aml 
JOIN account_account aa ON aml.account_id = aa.id 
JOIN account_move am ON aml.move_id = am.id 
WHERE aa.code_store->>'1' = '102012' AND am.state = 'posted';
-- Expected result: 0.00
```
