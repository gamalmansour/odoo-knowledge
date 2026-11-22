# Commission Cash-Only Paid Ratio, 3-Tier Credit Note Clawback, 100× Percentage Widget Trap & Odoo 19 Payroll Recompute

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `commission`, `out_refund`, `paid_ratio`, `widget-percentage`, `ir.cron`, `hr.payslip`, `compute_sheet`, `odoo19`

---

## Problem

Five high-impact financial & Odoo 19 bugs commonly hit custom sales commission, target, and payroll modules:

1. **Paying Commission on Unpaid Invoices via Partial Credit Notes:** Computing `paid_ratio = (amount_total - amount_residual) / amount_total` counts `out_refund` reconciliations as cash collected — paying positive commission on an invoice with **0 cash received** and mixing foreign invoice currency with company-currency `account.partial.reconcile.amount`.
2. **Missed Credit Note Clawbacks on Shortfall/Return Credit Notes:** Checking only `if move.reversed_entry_id:` misses every standalone `out_refund` (including visit shortfall credit notes linked via `sale_line_ids`), and attributing shortfall credit notes to `visit.salesperson_id` (the delivery driver) instead of `sale_order.user_id` deducts from the wrong user.
3. **100× Threshold Bypass (`widget="percentage"` vs `0–100` Scale):** Applying `widget="percentage"` to a `Float` field stores `80%` as `0.80`; comparing it against a `0–100` `achievement_pct` lets a rep at **0.8%** pass an **80%** gate!
4. **Odoo 19 `ir.cron` `NameError: name 'fields' is not defined`:** Cron Python code using `fields.Date.today()` fails on every run in Odoo 19 (use `datetime.date.today()`).
5. **Odoo 19 `hr.payslip` Silent 0-Commission & Multi-Sheet Overwrite:** Adding/removing `hr.payslip.input` lines without calling `payslip.compute_sheet()` leaves pre-computed payslip lines unchanged, and filtering inputs by `input_type_id` alone causes a second commission sheet in the same period to overwrite/delete the first.

## Root Cause

- `amount_residual` decreases for both cash payments (`entry`) and credit notes (`out_refund`); `account.partial.reconcile.amount` is always in **company currency** while `account.move.amount_total` is in **invoice currency**.
- `widget="percentage"` multiplies/divides by 100 in the web client (`0.80` in DB = `80%` in UI), incompatible with `achievement_pct = achieved / target * 100.0`.
- In Odoo 19 Enterprise `hr_payroll`, `hr.payslip.input` requires `payslip.version_id` (related required field) and `hr.payslip` does not auto-recompute salary lines when inputs change.

## Solution ✅

### 1. Cash-Only Multi-Currency `paid_ratio`
```python
inv_total_company = abs(move.amount_total_signed)
receivables = move.line_ids.filtered(lambda ml: ml.account_id.account_type == 'asset_receivable')
collected_company = sum(p.amount for p in receivables.matched_credit_ids if p.credit_move_id.move_id.move_type != 'out_refund')
refunded_company = sum(p.amount for p in receivables.matched_credit_ids if p.credit_move_id.move_id.move_type == 'out_refund')
net_collectible = max(0.0, inv_total_company - refunded_company)
paid_ratio = min(1.0, collected_company / net_collectible) if (net_collectible > 0 and collected_company > 0) else 0.0
```

### 2. 3-Tier Credit Note Clawback + Clean Unpost Unwind
- **Tier 1:** `move.reversed_entry_id` (standard credit note wizard).
- **Tier 2:** `move.invoice_line_ids.mapped('sale_line_ids.invoice_lines.move_id')` filtered to posted `out_invoice` (traces visit shortfall credit notes back to the original salesperson's invoice even when `reversed_entry_id` is empty).
- **Tier 3:** Pure standalone `out_refund` → negative commission record (`sign=-1.0`) for `move.invoice_user_id`.
- In `_unwind_commission_for_unpost()`, unlink both direct `salesperson.commission` AND any `salesperson.commission.line` where `source_refund_id == move.id` (blocking if settled).

### 3. Safe `noupdate="1"` Cron Code Repair in Existing DBs
```xml
<function model="account.move" name="_fix_commission_cron_code"/>
```
Replace only `'fields.Date.today()'` → `'datetime.date.today()'` in `cron.code` without touching `active` or `nextcall`.

### 4. Payroll Bridge (`hr.payslip.input` Ownership + `compute_sheet()` + Non-HR Sales Managers)
- Track `payslip_input_id = fields.Many2one('hr.payslip.input', ondelete='set null')` per commission sheet.
- Scope `.sudo()` employee/payslip lookup by `company_id` and `credit_note = False`, verify `payslip.version_id`, and call `payslip.compute_sheet()` after both payout and reversal.
- Guard `payslip_id` in XML with `groups="hr_payroll.group_hr_payroll_user"` and expose a stored `payslip_name` Char with `groups="!hr_payroll.group_hr_payroll_user"` so Sales Managers never hit `AccessError`.

## ⚠️ Pitfalls

- **Never put `widget="percentage"` on a `0–100` Float** — use plain Float (or store `0.0–1.0` consistently everywhere, never mix!).
- **Always freeze `settled_amount` on settlement confirmation** so later invoice payments or credit notes never silently mutate an already-paid settlement's `total_amount`.
- **Always refresh stored target achievements (`target._refresh_achievement()`) and exclude `draft` targets** before checking minimum thresholds or awarding period bonuses.

## Verification

- Playwright + JSON-RPC E2E suite verifying: cron execution, 50% credit note + 0 cash = `0.00` earned, real cash payment = full net commission, credit note unpost removes clawback, Tier-2 shortfall CN deducts from sales rep (not delivery driver), 80% threshold blocks 50% achievement, target bonus paid at most once per period, `action_cancel` releases commissions, Sales Manager pays & reverses 2 non-overlapping sheets on the same `hr.payslip` without `AccessError`.

## References

- Related file: `security/portal-savepoint-hidden-form-and-upload-hardening.md`
