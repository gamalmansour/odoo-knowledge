# Saudi SASO/SABER Conformity, LCGPA Mandatory National Products List & MWAN C&D Waste Manifest Compliance

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-arabia`, `saber`, `saso`, `lcgpa`, `mandatory-list`, `mwan`, `c-and-d-waste`, `balady`, `procurement`, `material-requisition`

---

## Problem

Construction contractors operating in the Kingdom of Saudi Arabia (KSA) face stringent statutory compliance regulations spanning material procurement and site operations:

1. **LCGPA Mandatory National Products List (القائمة الإلزامية للمنتجات الوطنية):** Under Government Tender and Procurement Law (GTPL) and Local Content and Government Procurement Authority (LCGPA / هيئة المحتوى المحلي) regulations, contractors are legally forbidden from purchasing imported alternatives for construction materials on the Mandatory List (e.g., rebar, cement, concrete blocks, electrical cables, pipes, ceramic tiles) unless an official statutory exemption is documented (unavailability in market, technical incompatibility, or price discrepancy exceeding 10%). Procurement audits impose financial penalties and disqualification for unauthorized imported goods.
2. **SASO / SABER Import Conformity (منصة سابر والمواصفات السعودية):** For imported building materials subject to SASO technical regulations, site entry and customs clearance require active Product (PCoC) and Shipment (SCoC) Conformity Certificates registered on the SABER platform. Material requisitions without valid SABER numbers stall at site receiving.
3. **Saudi MWAN C&D Waste Regulations (المركز الوطني لإدارة النفايات - موان):** Under Royal Decree No. (M/35) and Municipal (Balady) regulations, no construction and demolition (C&D) waste can leave the construction site without an official MWAN Waste Transport Manifest (وثيقة نقل النفايات), an MWAN-licensed carrier, registered driver National ID/Iqama, truck license plate, and certified weighbridge scale ticket (تذكرة الميزان) issued by an approved landfill or recycling plant. Unregulated dumping carries municipal stop-work orders and fines up to SAR 100,000.

---

## Root Cause

Standard ERP implementations treat material requisitions and waste registers as generic internal inventory moves:
- Material Purchase Requisitions (MRs) generate RFQs/POs purely based on quantity and budget, oblivious to whether the specified item is legally restricted to national manufacturing or requires a SABER certificate.
- Construction waste disposal records (`construction.waste.record` / `stock.scrap`) confirm and deduct stock without recording who hauled the debris, which landfill accepted it, or whether municipal and environmental waste manifests were filed.

---

## Solution ✅

### 1. LCGPA Mandatory List & SABER Enforcement in Material Requisition

In `models/material_purchase_requisition.py`:
- Extend `product.template` with `is_saber_regulated`, `saber_cert_number`, `saber_cert_expiry`, and `is_lcgpa_mandatory`.
- In requisition lines, compute `is_national_product` based on `country_of_origin_id.code == 'SA'`.
- Enforce statutory exemption codes: `['unavailable', 'technical_spec', 'price_diff_10']`.
- Block requisition department approval and PO generation whenever an unexempted imported item is requisitioned for a mandatory category:

```python
# LCGPA Mandatory Product & SABER Check
@api.depends('is_lcgpa_mandatory', 'is_national_product', 'lcgpa_exemption_reason', 'lcgpa_exemption_ref')
def _compute_lcgpa_violation(self):
    for line in self:
        if line.is_lcgpa_mandatory and not line.is_national_product:
            line.is_lcgpa_violation = not bool(line.lcgpa_exemption_reason and line.lcgpa_exemption_ref)
        else:
            line.is_lcgpa_violation = False

# Approval Gate
def action_department_approve(self):
    for rec in self:
        violations = rec.requisition_line_ids.filtered('is_lcgpa_violation')
        if violations:
            raise ValidationError(_(
                "LCGPA Compliance Block: Requisition cannot be approved because lines contain imported products "
                "on the Saudi Mandatory National Products List without documented exemption."
            ))
        saber_invalid = rec.requisition_line_ids.filtered(lambda l: l.is_saber_regulated and not l.is_national_product and not l.is_saber_valid)
        if saber_invalid:
            raise ValidationError(_(
                "SASO / SABER Compliance Block: Regulated imported materials require valid SABER certification."
            ))
```

### 2. MWAN C&D Waste Manifest & Disposal Scale Verification

In `models/waste.py`:
- Track `is_saudi_mwan_regulated`, `mwan_manifest_no`, `mwan_manifest_date`, `mwan_hazard_level`, `transporter_id`, `transporter_mwan_license`, `driver_civil_id`, `truck_plate_no`, `landfill_facility_name`, `landfill_permit_no`, and `weighbridge_ticket_no`.
- In `_validate_before_confirm()`, block off-site disposal (`disposition in ('recycle', 'scrap', 'landfill')`) if the MWAN manifest or licensed carrier is missing.
- Extend `res.partner` with `mwan_license_no` and `mwan_license_expiry`, checking for expired licenses prior to confirmation.

```python
# MWAN Compliance Gate in _validate_before_confirm()
if self.is_saudi_mwan_regulated and self.disposition in ('recycle', 'scrap', 'landfill'):
    if not self.mwan_manifest_no:
        raise ValidationError(_(
            "Saudi MWAN Compliance Block: Waste record '%(name)s' is marked for off-site disposal "
            "but lacks an official MWAN Transfer Manifest Number (رقم وثيقة نقل موان).",
            name=self.name))
    if not self.transporter_id or not self.transporter_mwan_license:
        raise ValidationError(_(
            "Saudi MWAN Compliance Block: Off-site waste transfer requires a certified waste transporter "
            "with a valid MWAN license number."
        ))
    if self.transporter_id.mwan_license_expiry and self.transporter_id.mwan_license_expiry < fields.Date.today():
        raise ValidationError(_(
            "Saudi MWAN Compliance Block: Transporter '%(transporter)s' has an expired MWAN license.",
            transporter=self.transporter_id.name))
    if self.mwan_hazard_level == 'hazardous' and not self.landfill_permit_no:
        raise ValidationError(_(
            "Saudi MWAN Compliance Block: Hazardous waste requires a certified disposal facility permit number."
        ))
```

---

## ⚠️ Pitfalls

1. **Do Not Require SABER for National (Saudi) Products:** Saudi products certified with the SASO Quality Mark (علامة الجودة السعودية) or local factory SASO standards do not use SABER shipment certificates (SCoC). Always guard SABER validation with `not line.is_national_product`.
2. **Allow Scale Slip Updates Post-Confirmation:** When a debris hauler departs site, the record is confirmed so stock is deducted and the transport manifest is authorized. The weighbridge scale ticket and net weight are obtained only after the truck dumps at the disposal facility. Never lock `weighbridge_ticket_no` or `net_weight_tons` in `_LOCKED_FIELDS`.
3. **Regex for Saudi Driver Civil ID:** Always use `^[12][0-9]{9}$` rather than `\d`, as Python's `\d` matches Arabic-Indic numerals that cause downstream API and printing failures.
4. **Distinguish On-Site Reuse vs. Off-Site Disposal:** Waste with disposition `reuse` (used on site as backfill/aggregate) or `return_supplier` does not leave the project boundary and must not trigger MWAN off-site manifest blocks.

---

## Verification

Run the automated test suite in `construction_material_requisition`:
```bash
python3 -m unittest construction_material_requisition.tests.test_saudi_material_compliance
```

Verify XML views and Python syntax across both modules:
```bash
python3 -m py_compile construction_material_requisition/models/material_purchase_requisition.py \
    construction_material_requisition/tests/test_saudi_material_compliance.py \
    construction_waste/models/waste.py
python3 -c "import xml.etree.ElementTree as ET; ET.parse('construction_material_requisition/views/material_purchase_requisition_views.xml'); ET.parse('construction_waste/views/waste_views.xml')"
```

---

## References

- Saudi Local Content and Government Procurement Authority (LCGPA): [Mandatory List of National Products](https://lcgpa.gov.sa/)
- Saudi Standards, Metrology and Quality Organization (SASO) & SABER Platform: [SABER Electronic Platform](https://saber.sa/)
- Saudi National Waste Management Center (MWAN): [Waste Management Executive Regulations](https://mwan.gov.sa/)
- Related Knowledge Base entries:
  - `Best Practices/saudi-subcontractor-governance-gtpl-and-lcgpa-portal.md`
  - `Best Practices/saudi-public-works-etimad-ipc-governance.md`
  - `orm/side-register-must-move-stock-and-dedup-kpi.md`
