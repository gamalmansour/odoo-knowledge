# Saudi GTPL Bank Guarantees, Performance Handover Gates, and Advance Auto-Amortization

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-gtpl`, `bank-guarantee`, `amortization`, `advance-payment`, `performance-bond`, `etimad`, `clearances`

---

## Problem

In Saudi contracting and construction projects governed by the **Government Tender and Procurement Law (GTPL - نظام المنافسات والمشتريات الحكومية)** and its Executive Regulations, bank guarantees (Letters of Guarantee - LG) represent major financial commitments and statutory compliance liabilities. Contractors face three critical failures when managing LGs in standard ERPs:

1. **Advance Guarantee Trapping & Credit Ceiling Exhaustion:** When a contractor receives a 10% or 20% advance payment against an Advance Payment Guarantee, standard systems keep the full guarantee face value active with the bank until final project completion, despite recovering 50% to 90% of the advance across approved Interim Payment Certificates (IPCs). This unnecessarily freezes millions in banking credit facilities (السقف الائتماني) and incurs recurring quarterly bank commission charges.
2. **Premature Performance Bond Release & Article 75 Violations:** Releasing a Final Performance Bond (5%) before official Preliminary Handover (الاستلام الابتدائي) or before obtaining valid statutory clearances (Zakat & Tax certificate, GOSI clearance, and Saudization certificate) violates Article 75 of Saudi GTPL, risking severe administrative fines, suspension from the Etimad portal, and claim disputes.
3. **Lapsing of Bid Bonds (الضمان الابتدائي):** GTPL Article 34 establishes a 90-day statutory validity period for tender bid bonds. Lack of automated alerts or conversion mechanisms upon tender award leads to missed extensions, disqualification by the tender examination committee, or forfeiture of the guarantee.

---

## Root Cause

Standard accounting and treasury modules treat bank guarantees as standalone financial records completely decoupled from contract progress billing (`contract.progress.invoice`), government procurement portals (`Etimad`), and statutory regulatory clearance lifecycles.

---

## Solution ✅

Implement a fully integrated Saudi GTPL bank guarantee engine in `construction_finance` connected to `construction_contract`:

### 1. Dynamic Advance Payment Auto-Amortization (Articles 67-68 GTPL)
Automatically compute advance recovery across confirmed/approved IPCs under the contract, dynamically tracking active exposure:

```python
@api.depends(
    'amount', 'guarantee_type', 'saudi_guarantee_category',
    'contract_id.progress_invoice_ids.advance_recovery_amount',
    'contract_id.progress_invoice_ids.state'
)
def _compute_advance_amortization(self):
    for rec in self:
        is_advance = (
            rec.guarantee_type == 'advance' or
            rec.saudi_guarantee_category == 'advance_payment'
        )
        if is_advance and rec.contract_id:
            invoices = rec.contract_id.progress_invoice_ids.filtered(
                lambda inv: inv.state not in ('draft', 'cancel')
            )
            total_rec = sum(invoices.mapped('advance_recovery_amount'))
            rec.advance_total_recovered = min(rec.amount, total_rec)
            rec.advance_remaining_exposure = max(0.0, rec.amount - rec.advance_total_recovered)
            rec.advance_amortization_pct = (rec.advance_total_recovered / rec.amount * 100.0) if rec.amount else 0.0
        else:
            rec.advance_total_recovered = 0.0
            rec.advance_remaining_exposure = rec.amount
            rec.advance_amortization_pct = 0.0
```

### 2. Statutory Performance Bond Release Gate (Article 75 GTPL)
Guard the `action_release()` method to enforce completion of Preliminary Handover and verification of the 3 statutory certificates:

```python
def action_release(self):
    for rec in self:
        if rec.is_saudi_gtpl and (rec.guarantee_type == 'performance' or rec.saudi_guarantee_category == 'final_performance'):
            if not (rec.override_gtpl_release_gate and rec.override_gtpl_release_reason):
                missing = []
                if not rec.is_preliminary_handover_done:
                    missing.append(_("Preliminary Handover Protocol (محضر الاستلام الابتدائي)"))
                if not rec.zakat_cert_valid:
                    missing.append(_("Valid Zakat & Tax Certificate (شهادة الزكاة وضريبة الدخل السارية)"))
                if not rec.gosi_cert_valid:
                    missing.append(_("Valid GOSI Certificate (شهادة التأمينات الاجتماعية السارية)"))
                if not rec.saudization_cert_valid:
                    missing.append(_("Valid Saudization Certificate (شهادة السعودة السارية)"))
                if missing:
                    raise ValidationError(_(
                        "Saudi GTPL Compliance Violation (المادة 75 من نظام المنافسات والمشتريات الحكومية):\n"
                        "Cannot release Final Performance Bond before preliminary handover and fulfilling clearances:\n- %s"
                    ) % "\n- ".join(missing))
```

### 3. Official Bank Reduction Letter Generation
Provide a formal bilingual QWeb PDF report (`report/report_bank_guarantee_reduction.xml`) citing Saudi GTPL Articles 67 & 68 with the schedule of approved IPCs, total recovered amount, and the new requested reduced face value, enabling immediate credit line unfreezing.

---

## ⚠️ Pitfalls

1. **Draft/Unapproved IPCs:** Never amortize against draft or cancelled IPCs. Only count IPCs that have completed verification (`state not in ('draft', 'cancel')`).
2. **Commission vs Margin on Release:** The bank's issuing commission is non-refundable. When releasing or amortizing, return only the cash margin (`cash_margin_amount`). Never reverse the commission expense entry unless the guarantee is reset to draft prior to activation.
3. **Executive Overrides:** If a release must be processed under exceptional circumstances (e.g., bank facility renewal with a replacement guarantee), allow override strictly to users in `group_construction_finance_manager` and mandate an `override_gtpl_release_reason` logged in the audit chatter.

---

## Verification

1. Verify Python syntax and compilation:
   ```bash
   python3 -m py_compile $(find models -name "*.py")
   ```
2. Verify XML templates and report bindings:
   ```bash
   python3 -c "import xml.etree.ElementTree as ET; ET.parse('report/report_bank_guarantee_reduction.xml'); print('VALID')"
   ```

---

## References

- Saudi Government Tender and Procurement Law (نظام المنافسات والمشتريات الحكومية الصادر بالمرسوم الملكي رقم م/128) - Articles 34, 38, 67, 68, and 75.
- Related Knowledge Base entry: `Best Practices/saudi-public-works-etimad-ipc-governance.md`
