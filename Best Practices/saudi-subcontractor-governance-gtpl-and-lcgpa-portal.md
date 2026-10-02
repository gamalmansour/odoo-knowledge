# Saudi Subcontractor Governance: GTPL Articles 71-72 (30% Cap), Statutory Clearances & LCGPA Portal

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-arabia`, `subcontractor`, `gtpl`, `articles-71-72`, `lcgpa`, `monshaat`, `gosi`, `zakat`, `portal`, `statutory-clearances`

---

## Problem

In Saudi public works and infrastructure megaprojects (governed by the Government Tender and Procurement Law - GTPL), general contractors who engage subcontractors face severe compliance and financial liabilities:
1. **Breach of GTPL Article 71 (30% Subcontracting Cap):** GTPL Article 71 strictly limits subcontracting to a maximum of 30% of the total main contract value unless prior written approval is issued by the government entity / project owner. Exceeding this threshold without approval constitutes a material breach resulting in contract termination, guarantee liquidation, and blacklisting.
2. **Breach of GTPL Article 72 (Prohibition of Re-Subcontracting):** Article 72 strictly forbids a subcontractor from re-subcontracting or assigning works to a secondary subcontractor (Sub-subcontracting / بيع العقود).
3. **Statutory Clearance Deficiencies (GOSI, ZATCA, Qiwa, CR):** If a subcontractor’s GOSI certificate, ZATCA Zakat certificate, Qiwa Saudization certificate, or Commercial Registration (CR) expires, certifying their progress billing or issuing vendor bills violates joint liability regulations and halts the main contractor's IPC releases on the Ministry of Finance's Etimad platform.
4. **LCGPA Local Content & SME Audits:** Failure to capture Monsha'at SME classification and LCGPA certified scores from subcontractors leads to post-handover penalty deductions (up to 10% of contract value) during final government audits.

## Root Cause

Standard ERP implementations treat subcontracts as simple purchase orders or isolated work packages without:
- Calculating cumulative subcontracting ratios against the parent owner contract.
- Validating the presence of formal government approval letters before contract activation.
- Enforcing statutory clearance validation gates at progress billing certification.
- Providing subcontractors with a self-service portal to monitor and renew expiring compliance certificates.

## Solution ✅

### 1. Subcontracting Cap Tracking & GTPL Articles 71 & 72 Governance

Extend `contract.subcontractor` to compute both the individual subcontract ratio and cumulative project subcontracts ratio:

```python
@api.depends('contract_value', 'owner_contract_id.contract_value')
def _compute_subcontract_ratios(self) -> None:
    for rec in self:
        main_contract = rec.owner_contract_id
        main_val = main_contract.contract_value if main_contract else 0.0
        if main_val > 0.0 and rec.contract_value:
            rec.subcontract_ratio_pct = round((rec.contract_value / main_val) * 100.0, 2)
            all_subs = self.search([
                ('owner_contract_id', '=', main_contract.id),
                ('state', 'not in', ('draft', 'cancelled'))
            ])
            total_sub_val = sum(all_subs.mapped('contract_value'))
            rec.total_subcontracts_ratio_pct = round((total_sub_val / main_val) * 100.0, 2)
            rec.is_subcontract_cap_exceeded = rec.total_subcontracts_ratio_pct > 30.0
        else:
            rec.subcontract_ratio_pct = 0.0
            rec.total_subcontracts_ratio_pct = 0.0
            rec.is_subcontract_cap_exceeded = False
```

Enforce GTPL Articles 71 & 72 approval gates:

```python
def action_approve(self) -> None:
    for rec in self:
        if rec.is_saudi_gtpl_governed:
            if not rec.no_sub_subcontracting_pledge:
                raise ValidationError(_("Saudi GTPL Article 72: 'No Sub-Subcontracting Pledge' is required before approval."))
            if rec.is_subcontract_cap_exceeded and not rec.is_owner_approved:
                raise ValidationError(
                    _("Saudi GTPL Article 71 Cap Exceeded: Subcontracting ratio (%.2f%%) exceeds 30%%. "
                      "Formal written approval from the Government Entity / Employer is required.")
                    % rec.total_subcontracts_ratio_pct
                )
    return super().action_approve()
```

### 2. Statutory Clearance Validation Gates at Billing

In `contract.subcontractor.invoice`, enforce verification of GOSI, ZATCA, Qiwa, and CR before approval:

```python
def action_approve(self) -> None:
    for rec in self:
        if rec.is_clearance_blocked and not rec.clearance_override_allowed:
            raise ValidationError(
                _("Statutory Clearance Gate Block: Subcontractor '%s' has expired statutory clearances. "
                  "Active GOSI, Zakat, Saudization, and CR certificates are required before certifying payments.")
                % rec.partner_id.name
            )
    return super().action_approve()
```

### 3. Subcontractor Portal Self-Service

Provide a secure portal route where subcontractors can inspect their certificate validity, review itemized progress payment certificates, and submit renewed certificate details:
- Route: `/my/subcontract/<id>`
- Post Action: `/my/subcontract/<id>/update_clearance`

### 4. Periodic Performance Evaluations & HSE/QAQC Metric Feeds (`subcontractor.evaluation`)

Evaluate active subcontractors across four core pillars: Quality, Timeliness, Safety, and Cooperation (1-5 scale):
- Compute `score_overall` as a weighted average.
- Automatically feed site safety compliance from `hse.observation` (deducting 0.2 per unsafe act) and `hse.incident` (deducting 1.0 per incident) to generate a data-driven `suggested_safety_score`.
- Provide Pivot and Graph views (`action_subcontractor_evaluation`) for contractor performance benchmarking across projects.

## ⚠️ Pitfalls

- **Do Not Rely on Partner Creation Date:** Always validate clearance expiration dates (`cr_expiry`, `gosi_cert_expiry`, `zakat_cert_expiry`, `saudization_cert_expiry`) dynamically against `fields.Date.today()`.
- **Warning Window:** Implement a 30-day early warning threshold (`Expiring Soon`) so subcontractors and procurement managers are alerted before certificates expire.
- **Managerial Override Auditability:** If a contract manager overrides a clearance block for an urgent site payment, mandate a required `clearance_override_reason` and log it in the Chatter.

## Verification

```bash
# Verify Python code compilation
python3 -m py_compile $(find construction_subcontractor_portal -name "*.py")

# Verify XML views
python3 -c "import xml.etree.ElementTree as ET; ET.parse('views/contract_subcontractor_views.xml')"
```

## References

- Saudi Government Tender and Procurement Law (GTPL), Articles 71 & 72.
- Local Content & Government Procurement Authority (LCGPA) Guidelines.
- Related: `Best Practices/saudi-public-works-etimad-ipc-governance.md`
