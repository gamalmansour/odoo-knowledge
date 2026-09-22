# Construction Subcontract Backcharge Settlement Reversal & Fleet Fuel Theft Detection Pattern

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `backcharge`, `subcontractor`, `equipment`, `fuel`, `diesel`, `reversal`, `cbs`, `ipc`

---

## Problem

In large-scale construction projects:
1. **Subcontractor Backcharge Leakage & Double Deductions:**
   When contractor backcharges (raised from Quality NCR rework or site material damage/waste) are pulled into a Subcontractor Progress Certificate (IPC) for payment deduction, they transition to `settled`. If the commercial team rejects or resets the IPC back to `draft` for correction, the settled backcharges remain tagged or silently un-deducted, leading to lost financial deductions or double-deduction on subsequent billings.
2. **Fuel Theft & Diesel Shrinkage Undetected in Fleet Operations:**
   Heavy earthmoving machinery (excavators, wheel loaders, cranes) is fueled on remote sites via mobile tankers. Without hourly consumption standards (L/hr), equipment fuel vouchers are entered without validation, allowing diesel shrinkage, false meter logs, and meter rollbacks.

## Root Cause

- Missing two-way state synchronization between the parent settlement document (`contract.subcontractor.invoice`) and the source penalty records (`construction.backcharge`). Resetting the draft must explicitly restore source records to `state = 'confirmed'` and unlink `settle_invoice_id`.
- Non-monotonic meter entry allowing operators or data entry personnel to enter arbitrary or lower meter hours, creating negative or zero operating deltas.
- Lack of standard baseline comparison and automatic tolerance gating (>15% variance threshold) on machine refueling logs.

## Solution ✅

### 1. Two-Way Backcharge Settlement & Safe Reversal Pattern
In the subcontract progress invoice (`contract.subcontractor.invoice`):
```python
def action_pull_backcharges(self):
    """Pull outstanding confirmed backcharges into IPC deductions and lock them as settled."""
    self.ensure_one()
    backcharges = self.env['construction.backcharge'].search([
        ('subcontract_id', '=', self.contract_id.id),
        ('state', '=', 'confirmed'),
        ('settle_invoice_id', '=', False),
    ])
    total_deduction = sum(backcharges.mapped('total_amount'))
    self.other_deductions = (self.other_deductions or 0.0) + total_deduction
    backcharges.write({
        'state': 'settled',
        'settle_invoice_id': self.id,
    })

def action_reset_to_draft(self):
    """Safely release linked backcharges back to confirmed when IPC is reset to draft."""
    for rec in self:
        linked_bcs = self.env['construction.backcharge'].search([
            ('settle_invoice_id', '=', rec.id),
        ])
        if linked_bcs:
            total_bc = sum(linked_bcs.mapped('total_amount'))
            rec.other_deductions = max(0.0, (rec.other_deductions or 0.0) - total_bc)
            linked_bcs.write({
                'state': 'confirmed',
                'settle_invoice_id': False,
            })
        rec.state = 'draft'
```

### 2. Monotonic Meter Guard & Theft / Leakage Anomaly Detection
In `construction.equipment.fuel.log`:
```python
@api.constrains('meter_reading', 'previous_meter_reading')
def _check_meter_reading_monotonic(self) -> None:
    for rec in self:
        if rec.meter_reading < rec.previous_meter_reading:
            raise ValidationError(_(
                "Non-monotonic meter reading: Current reading (%(curr).2f) cannot be less than previous reading (%(prev).2f).",
                curr=rec.meter_reading,
                prev=rec.previous_meter_reading,
            ))

@api.depends('meter_reading', 'previous_meter_reading', 'liters', 'standard_consumption_rate', 'meter_unit')
def _compute_meter_and_consumption(self):
    for rec in self:
        delta = (rec.meter_reading or 0.0) - (rec.previous_meter_reading or 0.0)
        rec.delta_meter = max(0.0, delta)
        rate = (rec.liters / rec.delta_meter) if (rec.delta_meter > 0 and rec.liters > 0) else 0.0
        rec.consumption_rate = rate
        std_rate = rec.standard_consumption_rate or 0.0
        if std_rate > 0 and rate > 0:
            var_pct = ((rate - std_rate) / std_rate) * 100.0
            rec.variance_pct = var_pct
            rec.is_consumption_abnormal = var_pct > 15.0
        else:
            rec.variance_pct = 0.0
            rec.is_consumption_abnormal = False
```

## ⚠️ Pitfalls

- **Do NOT rely solely on `@api.onchange` for CBS or Project propagation:** Always provide a fallback assignment in `create()` for records generated via API, test suites, or background imports where client onchanges never fire.
- **Do NOT delete settled backcharges:** Enforce `ondelete='restrict'` or check `state != 'settled'` to preserve the audit trail for subcontractor dispute resolution.
- **Saudi VAT & Admin Markup:** Standard backcharge clauses in FIDIC/Saudi contracts permit a 10% administrative handling fee. Ensure base amount and administrative fee are split clearly for VAT compliance.

## Verification

Run end-to-end integration tests confirming:
1. Backcharge amount is successfully added to IPC deductions and settled.
2. Resetting IPC to draft drops the deduction and restores backcharge status to confirmed.
3. Fuel logs with >15% consumption over baseline trigger `is_consumption_abnormal = True` and require justification.
4. Meter rollbacks raise a hard `ValidationError`.
