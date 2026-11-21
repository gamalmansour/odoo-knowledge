# Saudi SADAD Government Pass-Through Fees vs. ZATCA Phase 2 VAT (`VATEX-SA-OOS`) in Odoo 19

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-21                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-arabia`, `zatca`, `sadad`, `pass-through`, `disbursement`, `VATEX-SA-OOS`, `l10n_sa_edi`

---

## Problem

> Consulting firms, engineering offices, and service providers in Saudi Arabia frequently pay government SADAD bills (e.g., NCEC permit fees, Balady/MODON fees, customs/licensing disbursements) on behalf of their clients and include them on the client invoice for reimbursement alongside their consulting fees.
>
> If these SADAD fees are billed as ordinary service products:
> 1. **Double/Wrong VAT:** Odoo applies 15% Saudi VAT to a government fee that is **Out of Scope of VAT**.
> 2. **Inflated Revenue (P&L Distortion):** The pass-through amount posts to an Income account instead of a Balance-Sheet Clearing/Disbursement account, overstating gross revenue and Zakat/Tax base.
> 3. **ZATCA Phase 2 Rejection:** Leaving 0% tax without a valid `l10n_sa_exemption_reason_code` (`VATEX-SA-OOS`) causes UBL 2.1 XML validation errors in `l10n_sa_edi`.

## Root Cause

> Standard Odoo `account.move.line` routes product lines to `product_tmpl_id.get_product_accounts()` (Income/Expense) and defaults taxes from the product or company default sales tax (15% VAT in `l10n_sa`). Furthermore, in Odoo 19:
> - `account.move.line` uses `_get_computed_taxes()` and `tax_ids` (not `tax_id`).
> - `account.move.line._compute_account_id()` delegates product account resolution directly to `product.template.get_product_accounts(fiscal_pos=fiscal_pos)`.

## Solution ✅

> Flag pass-through government fee products (`is_sadad_pass_through = True`) and configure a company-level **Disbursement Clearing Account** (`asset_current` / `liability_current`) plus a **0% Out-of-Scope Tax** (`l10n_sa_exemption_reason_code = 'VATEX-SA-OOS'`).

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_sadad_pass_through = fields.Boolean(string='SADAD Government Pass-Through Fee')

    def get_product_accounts(self, fiscal_pos=None):
        accounts = super().get_product_accounts(fiscal_pos=fiscal_pos)
        if self.is_sadad_pass_through:
            company = self.company_id or self.env.company
            if company.env_sadad_account_id:
                accounts['income'] = company.env_sadad_account_id
                accounts['expense'] = company.env_sadad_account_id
        return accounts


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_computed_taxes(self):
        if (
            self.product_id
            and self.product_id.is_sadad_pass_through
            and self.move_id.is_sale_document(include_receipts=True)
        ):
            oos_tax = self.move_id.company_id.env_sadad_oos_tax_id
            return oos_tax if oos_tax else self.env['account.tax']
        return super()._get_computed_taxes()
```

Add an `action_post()` validation guard on `account.move` raising `ValidationError` if any customer invoice line with `is_sadad_pass_through=True` carries a tax with `amount != 0.0`.

## ⚠️ Pitfalls

- **Odoo 19 Field Renames:** Always use `tax_ids` (never `tax_id`) on `sale.order.line`, `purchase.order.line`, and `account.move.line`, and `product_uom_id` (never `product_uom`) on `sale.order.line` / `purchase.order.line`.
- **Do NOT Override `_get_computed_account()`:** It does not exist in Odoo 19 `account.move.line`; override `product.template.get_product_accounts()` instead so both Sales Invoices and Vendor Disbursement Bills hit the exact same clearing account (net P&L = 0.00 SAR).
- **ZATCA OOS Tax Code:** Ensure the 0% sales tax has `l10n_sa_exemption_reason_code = 'VATEX-SA-OOS'` (`VATEX-SA-OOS Not subject to VAT.`), verified in `addons/l10n_sa_edi/models/account_tax.py`.

## Verification

1. Create a Customer Invoice with 1 Consulting Fee line (15% VAT) + 1 SADAD Pass-Through line.
2. Confirm the SADAD line automatically picks the Balance-Sheet Clearing Account and `VATEX-SA-OOS` 0% tax.
3. Manually force 15% VAT onto the SADAD line and click **Confirm** — verify `ValidationError` blocks posting.

## References

- Core ZATCA codes: `addons/l10n_sa_edi/models/account_tax.py`
- Related file: `Best Practices/saudi-realestate-rett-vs-zatca-phase2-compliance.md`
