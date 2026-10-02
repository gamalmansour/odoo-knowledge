# Halala Rounding Absorption and Non-Destructive Restructuring in Real Estate Payment Plans

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `realestate`, `installments`, `rounding`, `halala`, `restructuring`, `account-moves`

---

## Problem

In real estate development and off-plan sales (e.g. Saudi Wafi projects), dividing high-value contracts across 36 to 60 periodic installments leads to recurring decimals (e.g. SAR 2,500,000 / 36 = 69,444.4444...). When each installment line is rounded to two decimal places, two critical defects emerge:

1. **Halala Rounding Mismatch:** The sum of rounded installment lines differs from the contract total by several halalas/cents (e.g. 2,499,999.84 vs 2,500,000.00). This breaks reconciliation upon unit handover and triggers `@api.constrains` failures.
2. **Destructive Restructuring:** When a customer requests payment rescheduling, naive wizard implementations call `unit.installment_ids.unlink()`. This deletes previously paid installments that are linked to posted customer advance invoices (`account.move`), corrupting historical accounting and audit trails.

## Root Cause

1. Python's floating-point division without tail absorption leaves accumulated fractional cents unallocated.
2. Blanket `.unlink()` calls on one2many collections fail to filter out settled records with financial journal links.

## Solution ✅

### 1. Halala Rounding Absorption Algorithm

In the installment generation engine, allocate the exact residual difference to the final periodic installment (or down payment) before creating database records:

```python
# Calculate regular installments
remaining_pool = total_amount - down_payment_amount - handover_payment_amount
per_installment = round(remaining_pool / num_installments, 2)

lines_vals = []
for i in range(1, num_installments + 1):
    lines_vals.append({
        'name': f'Installment #{i}',
        'amount': per_installment,
        'installment_type': 'installment',
        'due_date': current_date,
    })
    current_date += interval

# Exact halala absorption on the last periodic line
current_sum = sum(l['amount'] for l in lines_vals) + down_payment_amount + handover_payment_amount
halala_diff = round(total_amount - current_sum, 2)

if halala_diff != 0.0 and lines_vals:
    lines_vals[-1]['amount'] = round(lines_vals[-1]['amount'] + halala_diff, 2)
```

### 2. Non-Destructive Restructuring Safeguard

When regenerating or rescheduling a unit's payment plan, strictly partition paid vs unpaid installments:

```python
# Calculate schedule only on the outstanding balance
unpaid_balance = unit.balance_due if unit.total_paid > 0 else unit.list_price

# Only unlink unpaid lines; preserve paid lines and their account.move links
unpaid_installments = unit.installment_ids.filtered(lambda l: l.state not in ('paid',))
unpaid_installments.unlink()

# Generate new lines for the unpaid balance only
```

### 3. Milestone Overdue Guard in Daily Cron

Prevent construction milestone installments from prematurely marking as `overdue` when site work is delayed:

```python
overdue = self.search([
    ('due_date', '<', fields.Date.today()),
    ('state', 'not in', ['paid', 'cancelled']),
    '|', ('due_on_milestone', '=', False), ('is_milestone_achieved', '=', True),
])
```

## ⚠️ Pitfalls

- **Never unlink paid lines:** Always check `rec.state == 'paid'` or `rec.account_move_id` before deleting.
- **Enforce exact equality:** Add `@api.constrains` checking `abs(sum(installment_ids.mapped('amount')) - list_price) < 0.01`.

## Verification

1. Generate 36 installments for SAR 2,500,000.00. Verify `sum(installment_ids.mapped('amount')) == 2500000.00` down to the exact halala.
2. Mark 2 installments as paid (`action_register_payment`).
3. Re-run the installment wizard in restructure mode. Verify the 2 paid lines remain intact and new lines sum to `balance_due`.

## References

- Related file: `views/act-window-with-no-menuitem-or-button-is-dead-ui.md`
