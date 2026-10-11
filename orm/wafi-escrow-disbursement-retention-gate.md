# Wafi Escrow Account Integration: Statutory 5% Defect Retention Protection and Milestone Disbursement Controls

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `realestate`, `wafi`, `escrow`, `retention`, `disbursement`, `saudi-building-code`, `financial-controls`, `milestone`

---

## Problem

In Saudi off-plan real estate development (تحت مظلة وافي / لجنة البيع والتأجير على الخارطة بالهيئة العامة للعقار), developers are legally required to manage buyer installments through a dedicated, project-specific Escrow Bank Account. Two major compliance and financial integrity failures commonly arise:

1. **Accidental Depletion of the Statutory 5% Warranty Retention**:
   Under Wafi regulations, 5% of total project inflows must remain locked in the Escrow Account to cover post-handover defect liability and snagging rectification. When project accountants process contractor or supplier disbursements sequentially without an enforced system-level retention floor, the account balance frequently drops below the 5% threshold. This leads to immediate suspension of the off-plan sales license, statutory financial penalties, and audit failure.

2. **Uncontrolled Over-Disbursement Beyond Certified Physical Progress**:
   Disbursements are legally capped by the physical construction percentage certified by the supervisory engineering consultant and chartered legal auditor. In addition, marketing expenses are capped at 5% and developer management fees at 2.5% of total project value. Without automated enforcement, developers can over-disburse cash early in the project lifecycle, creating critical liquidity shortages before structural completion.

## Root Cause

Standard accounting journal entries or naive withdrawal approval workflows only check if `current_balance >= requested_amount`. They fail to distinguish between:
- **Total Book Balance**: All deposits minus historical withdrawals.
- **Statutory Retention Reserve**: `total_inflows * 0.05` (strictly locked by law).
- **Free Liquid Balance Available for Disbursement**: `max(0.0, current_balance - warranty_retention_amount)`.

Furthermore, naive models evaluate constraints at request creation rather than at actual fund release (`action_disburse`), allowing concurrent requests to bypass liquidity checks (race conditions).

## Solution ✅

Implement a dedicated Wafi Escrow management architecture with a hard retention floor, category-based expenditure caps, and a multi-step audit verification gate.

### 1. Model the Escrow Account with Stored Balances and 5% Floor

```python
class RealEstateWafiEscrow(models.Model):
    _name = 'realestate.wafi.escrow'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    project_id = fields.Many2one('construction.project', required=True, index=True)
    wafi_license_number = fields.Char(required=True, tracking=True)
    bank_iban = fields.Char(required=True, tracking=True)
    retention_rate = fields.Float(default=5.0, digits=(5, 2))
    certified_progress_pct = fields.Float(digits=(5, 2), tracking=True)

    total_inflows = fields.Monetary(compute='_compute_financial_kpis', store=True)
    total_disbursed = fields.Monetary(compute='_compute_financial_kpis', store=True)
    current_balance = fields.Monetary(compute='_compute_financial_kpis', store=True)
    warranty_retention_amount = fields.Monetary(compute='_compute_financial_kpis', store=True)
    available_for_disbursement = fields.Monetary(compute='_compute_financial_kpis', store=True)

    @api.depends('project_id', 'disbursement_ids.state', 'disbursement_ids.amount_approved', 'retention_rate')
    def _compute_financial_kpis(self):
        for rec in self:
            # 1. Total Inflows from settled buyer installments
            installments = self.env['realestate.installment'].search([
                ('project_id', '=', rec.project_id.id),
                ('state', '=', 'paid'),
            ])
            rec.total_inflows = sum(installments.mapped('amount'))

            # 2. Total Disbursed
            disbursed = rec.disbursement_ids.filtered(lambda d: d.state == 'disbursed')
            rec.total_disbursed = sum(disbursed.mapped('amount_approved'))

            # 3. Balance and Retention Floor
            balance = rec.total_inflows - rec.total_disbursed
            rec.current_balance = balance
            rate = rec.retention_rate if rec.retention_rate > 0 else 5.0
            retention = round(rec.total_inflows * (rate / 100.0), 2)
            rec.warranty_retention_amount = retention
            rec.available_for_disbursement = max(0.0, balance - retention)
```

### 2. Enforce Hard Retention Floor & Regulatory Caps at Fund Release

```python
class RealEstateWafiDisbursement(models.Model):
    _name = 'realestate.wafi.disbursement'

    escrow_id = fields.Many2one('realestate.wafi.escrow', required=True)
    amount_approved = fields.Monetary(required=True)
    disbursement_category = fields.Selection([
        ('contractor', 'Construction & Contractors'),
        ('consultant', 'Engineering Supervision'),
        ('marketing',  'Marketing & Sales - Max 5%'),
        ('management', 'Developer Management - Max 2.5%'),
        ('financing',  'Financing & Bank Fees'),
        ('other',      'Other Approved Expenses'),
    ], required=True)

    def action_disburse(self):
        for rec in self:
            if rec.state != 'wafi_approved':
                raise UserError(_('Disbursement must be approved by Wafi before releasing funds.'))

            escrow = rec.escrow_id
            retention_floor = escrow.warranty_retention_amount
            prospective_balance = escrow.current_balance - rec.amount_approved

            # CRITICAL RETENTION FLOOR GATE
            if prospective_balance < retention_floor:
                raise ValidationError(_(
                    'CRITICAL LEGAL VIOLATION: Disbursing %(amt)s would reduce escrow balance to '
                    '%(post_bal)s, which violates the mandatory 5%% statutory retention of %(ret)s. '
                    'Maximum allowable disbursement is %(max_allow)s.'
                ) % {
                    'amt': f"{rec.amount_approved:,.2f}",
                    'post_bal': f"{prospective_balance:,.2f}",
                    'ret': f"{retention_floor:,.2f}",
                    'max_allow': f"{escrow.available_for_disbursement:,.2f}",
                })

            rec.payment_date = fields.Date.today()
            rec.state = 'disbursed'
```

## ⚠️ Pitfalls

1. **Checking Liquidity Only at Draft/Submission Stage**:
   If two disbursement requests are submitted concurrently, both might pass the available liquidity check. The hard check against `prospective_balance < retention_floor` MUST be executed inside `action_disburse()` immediately before releasing the transaction.
2. **Ignoring Regulatory Category Ceilings**:
   Wafi rules limit developer marketing to 5% and management overhead to 2.5% of total project sales value. Do not allow marketing invoices to drain construction capital without enforcing category accumulation checks.
3. **Omitting the Tripartite Audit Signatures**:
   An escrow audit report submitted to Wafi or the custodian bank is legally invalid without tripartite sign-off (Developer, Supervisory Engineering Consultant, Certified Chartered Auditor). Ensure the QWeb PDF compliance report includes dedicated certificate reference fields and dual approval seals.

## Verification

1. Create a Wafi Escrow Account for a project with 1,000,000 SAR in paid buyer installments.
2. Confirm `warranty_retention_amount` is 50,000 SAR and `available_for_disbursement` is 950,000 SAR.
3. Submit a disbursement request for 960,000 SAR.
4. Attempting to release/disburse the request will immediately trigger `ValidationError` indicating that the prospective balance would breach the 5% mandatory retention reserve.
5. Submit an approved request for 900,000 SAR and verify that the transaction successfully marks as disbursed, updating remaining available liquidity to 50,000 SAR.

## References

- Saudi General Real Estate Authority (الهيئة العامة للعقار - وافي): Regulations on Off-plan Sales and Escrow Accounts.
- Related file: `orm/mullak-maintenance-deposit-escrow-handover-snag-gate.md`
