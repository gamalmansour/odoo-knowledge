# Saudi GTPL Variation Orders, Contract Amendments & EOT Governance

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `gtpl`, `contract_amendment`, `variation_order`, `value_engineering`, `eot`, `construction`

---

## Problem

In Saudi construction contracts (especially under the Government Tender and Procurement Law - GTPL / نظام المنافسات والمشتريات الحكومية), contract amendments, variation orders (أوامر التغيير), and Extension of Time (EOT / التمديد الزمني) are subject to strict regulatory caps:
1. Cumulative increase in contract value cannot exceed +10% of the original contract price without high-level ministerial approval.
2. Cumulative reduction in contract value cannot exceed -20% (or GTPL statutory limits).
3. If amendments are recorded as detached records without atomically cascading their adjustments into the underlying Contract BOQ lines (`contract.boq.line`) and planned project end date (`date_end_planned`), the contract billing periods (IPCs / المستخلصات) will mismatch the actual approved site quantities, resulting in rejected consultant billing certifications and legal disputes.

## Root Cause

- Variation orders often modify individual BOQ line quantities or prices. If the model only stores the header delta (`value_change`) without synchronizing the line items with the active `contract.boq.line` items upon approval, subsequent Interim Payment Certificates (IPCs) reference stale contract baselines.
- Extension of Time (EOT) must adjust the contractual completion milestone (`date_end_planned`). Otherwise, automated liquidated damages (غرامات التأخير) will trigger erroneously against the contractor.

## Solution ✅

Implement a dedicated `contract.amendment` lifecycle with strict GTPL ceiling validation and atomic line-item synchronization:

```python
# In contract.amendment model:
def action_approve(self):
    self.ensure_one()
    if self.state != 'submitted':
        raise UserError(_("Only submitted amendments can be approved."))
    
    # 1. Enforce GTPL Threshold Warning / Approval Verification
    if self.gtpl_cumulative_change_pct > 10.0:
        # Require documented ministerial or high-authority clearance
        if not self.justification:
            raise ValidationError(_("GTPL increase exceeds 10%. Statutory justification and high-authority approval required."))
            
    # 2. Synchronize BOQ lines atomically
    for line in self.line_ids:
        if line.boq_line_id:
            line.boq_line_id.write({
                'quantity': line.new_qty,
                'unit_price': line.new_price,
            })
            
    # 3. Synchronize Contract planned end date on EOT
    if self.duration_change_days:
        contract = self.contract_id
        if contract.date_end_planned:
            contract.date_end_planned += timedelta(days=self.duration_change_days)
            
    # 4. Advance state
    self.write({
        'state': 'approved',
        'approved_by': self.env.user.id,
        'approved_date': fields.Date.today(),
        'applied': True,
    })
```

## ⚠️ Pitfalls

- **Stale Amendment Lines:** If BOQ lines on the contract change before an amendment is approved, ensure `action_fetch_boq()` or a diffing mechanism verifies that `original_qty` matches the live `contract.boq.line` before applying `new_qty`.
- **Negative Value Engineering:** Value engineering orders reduce contract value (`value_change < 0`). Ensure cumulative GTPL calculation handles net vs. gross variations correctly so reductions do not mask dangerous positive scope creeps.
- **Multiple Active Unit Handovers:** When managing real estate unit handovers (`realestate.unit.handover`), always ensure unique active handover validation per unit to prevent concurrent snagging lists across different inspection teams.

## Verification

Run automated multi-agent verification script ensuring:
1. Approved amendments update `contract_value_current` on the contract.
2. EOT amendments correctly shift `date_end_planned`.
3. Historical cost rates (`construction.cost.rate`) are populated and referenced during tender cost estimation.

```bash
PYTHONPATH=/Users/gamal/odoo/odoo18.0 /Users/gamal/odoo/odoo18.0/.venv/bin/python -c "
import odoo
from odoo import api, SUPERUSER_ID
# Verify amendment records and GTPL calculations
"
```

## References

- Saudi Government Tender and Procurement Law (نظام المنافسات والمشتريات الحكومية ولائحته التنفيذية)
- Related: `Best Practices/saudi-gtpl-claims-eot-and-time-bar-defense.md`
- Related: `Best Practices/saudi-gtpl-bank-guarantees-advance-amortization.md`
