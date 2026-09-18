# Saudi Public Works Contracting: Etimad Platform IPC Workflow, GTPL Delay Penalties (10% Cap), and Statutory Clearances

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-arabia`, `etimad`, `gtpl`, `ipc`, `contracting`, `gosi`, `zakat`, `liquidated-damages`

---

## Problem

When contractors in Saudi Arabia bill government or semi-governmental entities (Ministries, Municipalities, NEOM, Red Sea, Roshn), standard ERP Interim Payment Certificates (like FIDIC Red Book or AIA G702) cause severe payment freezes and audit rejections:

1. **Etimad Platform Desynchronization:** Payment claims must follow the Ministry of Finance Etimad approval workflow (Contractor -> Consultant -> Owner Representative -> Financial Controller -> MOF Payment Order). Without tracking the Etimad Claim ID and official approval stage, cashflow forecasting fails.
2. **Statutory Delay Penalty Violations:** Under Article 73 of the Saudi Government Tenders and Procurement Law (GTPL - نظام المنافسات والمشتريات الحكومية), liquidated damages (delay penalties) **cannot exceed 10% of the total contract value** (or 6% for supply/maintenance contracts). In standard ERPs, cumulative delay deductions are not capped, exposing the contractor or consultant to unlawful over-deductions and disputes.
3. **Missing Statutory Clearances (GOSI, Zakat, Saudization):** Government payment orders are legally blocked if any of the contractor's three mandatory clearances (GOSI, Zakat & Tax, Saudization) are expired on the date of certification.

## Root Cause

Standard construction ERP modules are built around international forms (FIDIC or AIA) that assume private commercial contracting. The Saudi public procurement framework is strictly statutory, regulated by the Ministry of Finance, Etimad Portal, and the Government Tenders and Procurement Law (Royal Decree M/128).

## Solution ✅

### 1. Model Structure (`contract.progress.invoice`)
Extend the IPC model to track the Etimad lifecycle, statutory clearances, and GTPL caps:

```python
# Etimad Stages
etimad_claim_id = fields.Char(string='Etimad Claim No.', tracking=True)
etimad_approval_stage = fields.Selection([
    ('draft', 'Draft Contractor Claim'),
    ('consultant_review', 'Consultant Review'),
    ('consultant_approved', 'Consultant Approved'),
    ('owner_representative', 'Owner Representative'),
    ('financial_officer', 'Financial Controller'),
    ('payment_order_issued', 'MOF Payment Order Issued'),
    ('paid', 'Disbursed'),
], default='draft', tracking=True)

# Statutory Clearances Validation
@api.depends('gosi_cert_number', 'gosi_cert_expiry', 'zakat_cert_number', 'zakat_cert_expiry', 'saudization_cert_number', 'saudization_cert_expiry')
def _compute_statutory_clearances(self):
    today = fields.Date.context_today(self)
    for rec in self:
        rec.is_gosi_valid = bool(rec.gosi_cert_number and (not rec.gosi_cert_expiry or rec.gosi_cert_expiry >= today))
        rec.is_zakat_valid = bool(rec.zakat_cert_number and (not rec.zakat_cert_expiry or rec.zakat_cert_expiry >= today))
        rec.is_saudization_valid = bool(rec.saudization_cert_number and (not rec.saudization_cert_expiry or rec.saudization_cert_expiry >= today))

# 10% Delay Penalty Ceiling Constraint
@api.constrains('ld_amount', 'is_saudi_government_ipc')
def _check_saudi_gtpl_ld_cap(self):
    for rec in self:
        if rec.is_saudi_government_ipc and rec.is_ld_cap_exceeded:
            raise ValidationError(_(
                "Statutory Violation Warning: Total cumulative delay penalties (%s) exceed the 10%% maximum ceiling (%s) "
                "mandated by Article 73 of the Saudi Government Tenders and Procurement Law."
            ) % (rec.total_cumulative_ld, rec.gtpl_ld_cap_amount))
```

### 2. Variation Order Limits (`contract.amendment`)
Saudi GTPL limits cumulative change orders to **+10% increase** and **-20% reduction** of the original contract sum without High Authority authorization. Monitor this ratio dynamically on every amendment.

### 3. Saudi Standard Public Works IPC Report
Generate an official bilingual report modeled on the Ministry of Finance Standard Public Works IPC, detailing gross completed works, advance payment amortization, retention deduction, delay penalties, clearance status, and the 5-signatory approval cycle.

## ⚠️ Pitfalls

- **Do NOT deduct retention on VAT:** In Saudi contracting, retention (5% or 10%) is calculated strictly on the **pre-tax gross amount** of completed works, NOT inclusive of 15% VAT.
- **Advance Payment Guarantee Amortization:** When advance payments are recovered on an IPC, ensure the corresponding bank guarantee is marked for reduction to release bank credit facilities.

## Verification

1. Create a government IPC linked to an Etimad claim.
2. If delay penalties exceed 10% of the contract value -> `ValidationError` triggers.
3. If GOSI, Zakat, or Saudization certs are expired -> Status badges highlight warnings.
4. Printable Saudi Public Works IPC renders with full 5-stage signatory credentials.

## References

- Saudi Government Tenders & Procurement Law (نظام المنافسات والمشتريات الحكومية م/128 - المواد 73 و 74)
- Ministry of Finance Etimad Financial Claims Portal Guidelines
