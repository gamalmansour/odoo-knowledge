# Preserving Historical Payer Identity & Clearance Gate in Real Estate Unit Resale

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `realestate`, `transfer`, `resale`, `installments`, `audit-trail`, `payer-identity`, `clearance`

---

## Problem

In real estate development, property units are frequently resold or transferred before final completion (حوالة حق وتنازل عن وحدة عقارية). 
When an off-plan unit is transferred from an existing buyer (Transferor) to a new buyer (Transferee):

If installment schedules link to the customer via a stored related field:
```python
partner_id = fields.Many2one(
    related='unit_id.partner_id',
    store=True,
    string='Buyer',
)
```
Updating `unit.partner_id = new_buyer.id` triggers an ORM recomputation on `installment.partner_id` across **all** installment records. As a consequence:
1. Past paid installments (e.g. 500,000 SAR paid over 2 years by the original buyer) are silently rewritten in the database to point to the new buyer.
2. Financial audit trails, ZATCA tax invoices, customer balance statements, and legal clearance certificates become corrupted because the original payer's identity is wiped out from historical schedules.
3. If the original buyer had unpaid overdue installments, transferring the unit without a mandatory financial clearance gate transfers or conceals bad debt, causing legal disputes when the new buyer denies liability.

---

## Root Cause

`related=..., store=True` fields without an immutable snapshot counterpart mirror live upstream state. When ownership changes, the ORM recomputes stored fields for the entire lifetime of the child records. Additionally, standard workflows often lack an enforced gate to audit outstanding matured payments before allowing ownership changes.

---

## Solution ✅

### 1. Two-Tier Partner Attribution on Installments
Separate the **current contracted debtor** from the **historical settling payer**:

```python
class RealEstateInstallment(models.Model):
    _inherit = 'realestate.installment'

    partner_id = fields.Many2one(
        related='unit_id.partner_id',
        store=True,
        string='Current Contracted Buyer',
    )
    payer_partner_id = fields.Many2one(
        'res.partner',
        string='Payer (Settled By)',
        readonly=True,
        copy=False,
        help="Actual party who settled this installment payment (immutable audit trail).",
    )

    @api.depends('due_date', 'account_move_id.payment_state')
    def _compute_state(self) -> None:
        for rec in self:
            if rec.account_move_id and rec.account_move_id.payment_state in ('paid', 'in_payment'):
                rec.state = 'paid'
                # Freeze payer identity at the moment of payment settlement
                if not rec.payer_partner_id:
                    rec.payer_partner_id = rec.account_move_id.partner_id.id or rec.unit_id.partner_id.id
```

### 2. Pre-Transfer Financial Clearance Gate & Overdue Block
Enforce a clearance audit before developer approval (NOC):

```python
def action_check_clearance(self):
    self.ensure_one()
    today = fields.Date.today()
    overdue = self.unit_id.installment_ids.filtered(
        lambda i: i.state not in ('paid', 'cancelled') and i.due_date and i.due_date < today
    )
    self.overdue_amount = sum(overdue.mapped('amount'))
    self.clearance_status = 'has_overdue' if self.overdue_amount > 0 else 'cleared'

def action_approve_noc(self):
    self.ensure_one()
    if self.clearance_status == 'has_overdue' and not self.allow_overdue_override:
        raise UserError(_("Cannot approve transfer while unit has overdue installments."))
    self.noc_number = f"NOC-{self.name}"
    self.state = 'approved'
```

### 3. Safe Ownership Handoff on Finalization
Before writing the new partner to the unit, ensure all past paid lines have their `payer_partner_id` locked:

```python
def action_execute_transfer(self):
    self.ensure_one()
    # Freeze payer on all paid installments prior to ownership reassignment
    for inst in self.unit_id.installment_ids.filtered(lambda i: i.state == 'paid'):
        if not inst.payer_partner_id:
            inst.payer_partner_id = self.old_partner_id.id

    # Update unit ownership
    self.unit_id.write({'partner_id': self.new_partner_id.id})
    self.state = 'done'
```

---

## ⚠️ Pitfalls

- **Do NOT delete or recreate paid installments:** Never unlink paid installments with linked `account.move` journal entries or invoices. Only the unit's future unpaid obligations are assumed by the transferee.
- **Do NOT invoice the developer administrative fee to the wrong party:** Developer NOC transfer fees (typically 2% to 2.5% in Saudi Arabia) must be explicitly billed to the agreed party (`new_buyer`, `old_buyer`, or `shared`).
- **Do NOT allow multiple concurrent active transfer requests:** Always add a constraint `_check_active_transfer_conflict` preventing overlapping transfer requests on the same unit.

---

## Verification

1. Create a unit, assign Buyer A, generate installments, and mark 2 installments as paid.
2. Confirm that `payer_partner_id` on the paid installments is set to Buyer A.
3. Open a transfer request to Buyer B, run clearance check, approve NOC, invoice fee, and execute transfer.
4. Verify that `unit.partner_id` is now Buyer B, but the 2 paid installments still permanently record Buyer A as the `payer_partner_id`.
