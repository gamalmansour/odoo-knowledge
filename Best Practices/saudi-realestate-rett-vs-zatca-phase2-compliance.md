# Saudi Real Estate Taxation: Handling RETT (5%) & First-Home Subsidy alongside ZATCA Phase 2 E-Invoicing

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-arabia`, `zatca`, `rett`, `real-estate`, `e-invoicing`, `taxes`, `first-home`, `rega`

---

## Problem

When building or deploying real estate sales and off-plan development modules in Saudi Arabia, developers often confuse **ZATCA E-Invoicing Phase 2 (`l10n_sa_edi`)** with **Real Estate Transaction Tax (RETT - ضريبة التصرفات العقارية)**:

1. **VAT 15% Misapplication:** Sales orders and invoices for property units are created with standard 15% VAT. Under Saudi Law (Royal Order A/84), real estate property sales are **strictly exempt from VAT**; charging VAT is a major statutory violation subject to heavy ZATCA fines.
2. **RETT 5% Misclassification:** Developers create a 5% tax in `account.tax` named "RETT 5%" and attach it to customer invoices. This erroneously pushes RETT into quarterly VAT declarations, which ZATCA Fatoora rejects because Phase 2 E-invoicing only recognizes VAT (15% or 0% / Exempt).
3. **Blocked Title Deed Conveyancing (إفراغ الصك):** Notaries (كتابة العدل) and the Real Estate Registry require an official **ZATCA RETT Assessment & Sadad bill number** or a validated First-Home Exemption certificate before executing the title deed transfer. Standard Odoo invoices lack these credentials.

## Root Cause

In the Saudi tax regime:
- **VAT (ضريبة القيمة المضافة):** Regulated under the VAT Law. Property sales are **Exempt from VAT** under Article 30 of the VAT Implementing Regulations (ZATCA official exemption code: `VATEX-SA-30`).
- **RETT (ضريبة التصرفات العقارية):** An entirely independent 5% tax enacted by Royal Order A/84, administered via a dedicated portal (`portal.zatca.gov.sa/rett`). It is paid directly via government Sadad bill numbers, NOT via corporate VAT returns.
- **First-Home Citizen Exemption (دعم المسكن الأول):** The Saudi government subsidizes first-time home buyers by exempting 5% of property value up to 1,000,000 SAR (a discount of up to 50,000 SAR borne by the State).

## Solution ✅

Decouple the accounting tax point from the regulatory property conveyancing lifecycle:

### 1. In Accounting / Sale Order (`account.move` & `sale.order`)
Set taxes to `0% Exempt` with ZATCA Phase 2 Reason Code `VATEX-SA-30`. This ensures the UBL 2.1 XML clears ZATCA Fatoora without validation errors:

```python
# Real estate sales must NOT carry 15% VAT
order_line = [(0, 0, {
    'product_id': property_product.id,
    'price_unit': contracted_price,
    'tax_id': [(6, 0, [])], # Or 0% VATEX-SA-30 tax
})]
```

### 2. In Real Estate Unit Model (`realestate.unit`)
Implement the full statutory RETT calculation and First-Home subsidy deduction:

```python
@api.depends('list_price', 'sale_order_id.amount_total', 'rett_applicable', 'is_first_home_buyer', 'rett_rate')
def _compute_rett_amounts(self):
    for rec in self:
        if not rec.rett_applicable:
            rec.rett_base_amount = 0.0
            rec.rett_exemption_amount = 0.0
            rec.rett_amount_due = 0.0
            continue
        base = rec.sale_order_id.amount_total if rec.sale_order_id else rec.list_price
        rec.rett_base_amount = base
        rate = (rec.rett_rate or 5.0) / 100.0
        if rec.is_first_home_buyer:
            # First Home Citizen Subsidy: State bears 5% on first 1,000,000 SAR (max 50,000 SAR)
            exempt_base = min(base, 1000000.0)
            rec.rett_exemption_amount = exempt_base * rate
            taxable_excess = max(0.0, base - 1000000.0)
            rec.rett_amount_due = taxable_excess * rate
            if rec.rett_amount_due <= 0.0 and rec.rett_status == 'draft':
                rec.rett_status = 'exempt'
        else:
            rec.rett_exemption_amount = 0.0
            rec.rett_amount_due = base * rate
```

### 3. Official RETT Statement Report
Generate a dedicated printable **RETT Assessment & Sadad Notification Statement** containing:
- 12-digit Electronic Title Deed Number (وزارة العدل).
- National Address (سبل SPL short code).
- First-Home Sakani Certificate Reference.
- ZATCA RETT Sadad Bill Number & Clearance Status.

## ⚠️ Pitfalls

- **Do NOT invoice broker commission as RETT:** Brokerage services are standard professional services subject to **15% VAT**, NOT 5% RETT!
- **REGA Val Brokerage Cap:** In Saudi Arabia, paying commission to a broker without an active Val License (رخصة فال) or exceeding the 2.5% statutory cap without written authorization violates REGA law.

## Verification

1. Unit sold for 800,000 SAR with First-Home Citizen flag -> RETT Due = 0 SAR, Status = Fully Exempt (`exempt`).
2. Unit sold for 1,500,000 SAR with First-Home Citizen flag -> Exemption = 50,000 SAR, Net RETT Due = 25,000 SAR (5% on 500,000 SAR excess).
3. Commercial / Investor Sale -> Standard 5% RETT on full value (75,000 SAR).
4. Accounting invoices clear ZATCA Phase 2 with `VATEX-SA-30` code.

## References

- Saudi ZATCA Real Estate Transaction Tax Regulations (الأمر الملكي أ/84)
- ZATCA E-Invoicing Phase 2 Technical Specifications (UBL 2.1)
- Odoo Core Exemption Mapping: `addons/l10n_sa_edi/models/account_tax.py` (`VATEX-SA-30`)
