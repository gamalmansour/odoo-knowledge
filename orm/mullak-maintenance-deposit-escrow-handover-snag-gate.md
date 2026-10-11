# Separating Mullak Maintenance Escrow Deposits & Enforcing Handover Snagging Gates

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `realestate`, `handover`, `mullak`, `maintenance-deposit`, `escrow`, `snagging`, `warranties`

---

## Problem

In off-plan and luxury real estate developments in Saudi Arabia, project handover (تسليم الوحدات) involves two major compliance challenges:
1. **Co-mingling Maintenance Escrow Deposits:** Developers collect a mandatory maintenance reserve deposit (5% to 8% of unit price) intended for the building's Owners Association (**Mullak / مُلاّك**). If this collection is invoiced as standard developer operating revenue, it distorts revenue recognition, inflates VAT liabilities, and leads to severe regulatory penalties when transferring funds to the association's bank account.
2. **Premature Handover with Critical Snags:** If the system permits executing the final handover action (`state = 'handed_over'`) without checking on-site inspection snagging observations, keys are handed over while major plumbing or electrical defects exist, triggering client disputes, negative audits, and withholding of maintenance deposits.

---

## Root Cause

Standard ERP sales flows equate "handover" with a simple status change or generic delivery order. They lack:
- A distinct custody/liability channel for non-operating escrow reserves.
- A programmatic barrier linking technical on-site defect logs (`realestate.handover.snag`) to the physical possession gate.

---

## Solution ✅

### 1. Distinct Custody/Escrow Channel for Maintenance Deposit
Invoice the deposit under a dedicated service product linked to a custody liability account rather than operating sales income:

```python
class RealEstateUnitHandover(models.Model):
    _name = 'realestate.unit.handover'

    maintenance_deposit_amount = fields.Monetary(
        string='Maintenance Deposit Amount',
        compute='_compute_maintenance_deposit',
        store=True,
    )
    maintenance_deposit_status = fields.Selection([
        ('pending', 'Pending Collection'),
        ('paid', 'Collected'),
        ('transferred_mullak', 'Transferred to Mullak'),
    ], default='pending', tracking=True)

    def action_invoice_maintenance_deposit(self):
        self.ensure_one()
        product = self.env['product.product'].search([('default_code', '=', 'REALESTATE_MULLAK_DEPOSIT')], limit=1)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'ref': _('Mullak Deposit — Unit %s') % self.unit_id.name,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'price_unit': self.maintenance_deposit_amount,
            })],
        })
        self.maintenance_deposit_invoice_id = invoice.id
```

### 2. Enforce Handover Gates Against Critical Snags & Unpaid Deposits
Block the final handover execution until inspection criteria are certified:

```python
def action_complete_handover(self):
    self.ensure_one()
    # Gate 1: Check for open critical defects
    if self.has_critical_snags:
        raise UserError(_(
            "Cannot complete handover: Critical defects remain unresolved on the snagging list."
        ))
    # Gate 2: Check maintenance deposit collection
    if self.maintenance_deposit_status == 'pending':
        raise UserError(_(
            "Cannot complete handover: Owners Association (Mullak) maintenance deposit is unpaid."
        ))

    # Trigger revenue recognition and unit handover
    self.unit_id.action_handover()
    self.delivery_date = fields.Date.today()
    self.state = 'delivered'
```

### 3. Baseline Warranties from Handover Protocol Date
Anchor all Saudi Building Code warranties (10-year structural & waterproofing, 2-year MEP) to the actual physical possession date `delivery_date`, preventing disputes regarding warranty start dates.

---

## ⚠️ Pitfalls

- **Do NOT allow key delivery before recording meter readings:** Always mandate capturing initial electricity and water meter serials and readings at the handover moment to protect the developer from post-occupancy consumption bills.
- **Do NOT skip reverse handover handlers:** If a handover is cancelled or unwound, ensure that accounting reversal (`action_reverse_handover`) and key return are executed symmetrically.

---

## Verification

1. Create a handover protocol for a sold unit with a critical snag.
2. Attempt to click `Deliver Unit & Keys` → Verify that `UserError` blocks the action.
3. Mark the snag as rectified, collect the maintenance deposit, and retry → Verify that handover succeeds, revenue/COGS recognition is posted, and unit state moves to `handed_over`.
