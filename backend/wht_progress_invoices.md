# Withholding Tax (WHT) on Subcontractor Progress Invoices

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 15, 16, 17                                 |
| Severity      | 🟢 Low                                    |
| Last Verified | 2026-07-08                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `WHT`, `Progress Invoices`, `Construction`, `Taxes`

---

## Problem

> When generating progress invoices for subcontractors, Withholding Tax (WHT) must be deducted. The challenge is ensuring that WHT is calculated correctly on the cumulative work done to-date, and then correctly allocated as a delta (Current WHT = WHT To-Date - Prior WHT) so that vendor bills only reflect the current period's tax deduction.

## Root Cause

> Standard Odoo taxes are line-based and applied on the current invoice amount. However, in construction progress billing, amounts are cumulative. If you apply a standard line tax, any rounding or changes in previous invoices might cause inconsistencies in the total WHT deducted across the project lifespan.

## Solution ✅

> Calculate WHT cumulatively and deduct the previously withheld amount to find the current deduction.

```python
# 1. Add fields to track WHT
wht_percent = fields.Float(string='WHT %', related='contract_id.wht_percentage', store=True)
wht_amount = fields.Monetary(string='WHT Deduction (Current)', compute='_compute_financials', store=True)
wht_to_date = fields.Monetary(string='WHT To-Date', compute='_compute_financials', store=True)

# 2. In _compute_financials, calculate cumulatively then delta
work_done_to_date = sum(rec.line_ids.mapped('cumulative_amount'))
wht_to_date = (rec.wht_percent / 100.0) * work_done_to_date

# Fetch prior invoices
prior_invoices = self.search([
    ('contract_id', '=', contract.id),
    ('state', 'in', ['approved', 'invoiced']),
    ('id', '!=', rec.id)
])

prior_wht_to_date = sum(prior_invoices.mapped('wht_amount'))
rec.wht_to_date = wht_to_date
rec.wht_amount = wht_to_date - prior_wht_to_date

# 3. Add to vendor bill creation as a separate negative line
if rec.wht_amount > 0:
    if not (profile and profile.account_wht_id):
        raise ValidationError(_('Please configure a Withholding Tax (WHT) Account in the Construction Profile.'))
    invoice_vals['invoice_line_ids'].append((0, 0, {
        'name': _('Withholding Tax (WHT)'),
        'quantity': 1,
        'price_unit': -rec.wht_amount,
        'account_id': profile.account_wht_id.id,
    }))
```

## ⚠️ Pitfalls

- **Validation:** Always validate that the WHT Account is configured in the settings or profile before generating the vendor bill. Otherwise, Odoo will raise an error if the negative line is assigned a default expense account incorrectly.
- **Rounding:** By using delta (`Current WHT = WHT To-Date - Prior WHT`), we avoid rounding errors accumulating over multiple progress invoices.

## Verification

> Create a progress invoice, set the WHT percentage, and verify that `wht_amount` correctly reflects the tax for the current billing period, and that the resulting vendor bill includes the negative deduction line mapped to the WHT liability account.
