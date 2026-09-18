# Saudi GTPL Etimad Tendering (Article 36 Bid Bonds & LCGPA Article 59) & Third-Party Equipment Safety Compliance (TÜV/SASO & Mega-Project Access)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-arabia`, `gtpl`, `etimad`, `tender`, `bid-bond`, `article-36`, `lcgpa`, `article-59`, `equipment-safety`, `tuv`, `saso`, `crane-inspection`, `aramco-sticker`, `neom`

---

## Problem

General construction contractors bidding and executing public works and mega-infrastructure projects across the Kingdom of Saudi Arabia (KSA) face strict statutory mandates at both the pre-award tendering stage and the post-award site mobilization stage:

1. **Etimad Platform & GTPL Article 36 Initial Guarantee (الضمان الابتدائي):** Under the Saudi Government Tender and Procurement Law (نظام المنافسات والمشتريات الحكومية - Royal Decree M/128), all public tenders submitted through the Etimad portal require an Initial Guarantee (Bid Bond) strictly between **1.0% and 2.0%** of the total bid value. Guarantees must be issued by a SAMA-licensed Saudi bank and remain legally valid for at least 90 days post-technical envelope opening. Submissions outside this percentage window or with defective bank guarantee letters are rejected by the tender evaluation committee with risk of temporary debarment.
2. **LCGPA Local Content (Article 59) & Contractor Classification (Balady):** Bids must calculate statutory Local Content pricing preference (10% evaluation preference for national companies per LCGPA regulations), pledge adherence to the Mandatory National Products List, and verify that the contractor's classification grade (تصنيف المقاولين - منصة بلدي) matches the tender's prescribed field and financial category.
3. **Heavy Plant & Mobile Crane Safety Inspection (TÜV/SASO & Civil Defense):** Under Saudi OSHA and Civil Defense safety codes, heavy construction plant (excavators, bulldozers, wheel loaders, pavers) cannot operate on site without periodic third-party safety inspection certificates issued by accredited inspection bodies (TÜV Rheinland/SÜD/Austria, Bureau Veritas, SGS, Applus+, or SASO accredited bodies). Mobile and tower cranes must have an additional certified Proof Load Test (SWL / فحص واختبار أجهزة ومهمات الرفع).
4. **Mega-Project Access Permits & Operator Licensing:** Mega-developers (Saudi Aramco, NEOM, Red Sea Global, Qiddiya, ROSHN, Royal Commission) require verified gate passes and site stickers. Furthermore, operators must hold valid Saudi Traffic Police (Muroor) heavy equipment driving licenses and recognized third-party competency operator cards. Operating uninspected machinery or deploying uncertified operators triggers immediate stop-work orders, contractual fines, and HSE safety disqualifications.

---

## Root Cause

Standard ERP systems treat tenders simply as generic CRM pipeline stages and equipment as basic fixed assets:
- **Tender Pipelines:** Odoo CRM/tenders allow quotation submission without checking statutory GTPL constraints (missing Etimad tender numbers, bid bond percentages outside the 1.0%–2.0% band, or expired bank guarantee letters).
- **Plant & Fleet Registers:** Equipment assets transition to `in_use` status based solely on project allocation or manager approval, without enforcing third-party safety certificates, crane lifting gear load test documents, site sticker expirations, or operator driving license validity.

---

## Solution ✅

### 1. Saudi GTPL & Etimad Governance in `construction_tender`

Extend `tender.opportunity` with GTPL statutory parameters, bid bond validation, and Local Content preference calculations:

```python
# Bid Bond Article 36 (1.0% to 2.0% Statutory Range)
@api.depends('is_saudi_gtpl', 'bid_bond_letter_amount', 'submitted_bid_amount')
def _compute_bid_bond_valid(self):
    for rec in self:
        if not rec.is_saudi_gtpl or not rec.submitted_bid_amount:
            rec.is_bid_bond_valid = True
            rec.bid_bond_pct = 0.0
            continue
        pct = (rec.bid_bond_letter_amount / rec.submitted_bid_amount) * 100.0
        rec.bid_bond_pct = pct
        # GTPL Article 36: Strictly 1.0% to 2.0% of total bid price
        rec.is_bid_bond_valid = (1.0 <= round(pct, 2) <= 2.0)

# LCGPA Article 59 Local Content Preference Adjustment
@api.depends('is_saudi_gtpl', 'submitted_bid_amount', 'lcgpa_target_pct')
def _compute_lcgpa_preference(self):
    for rec in self:
        if rec.is_saudi_gtpl and rec.submitted_bid_amount:
            # 10% statutory price preference evaluation model
            rec.lcgpa_preference_adjusted_amount = rec.submitted_bid_amount * 0.90
        else:
            rec.lcgpa_preference_adjusted_amount = rec.submitted_bid_amount

# Statutory Bid Approval Gate
def action_approve_bid(self):
    self.ensure_one()
    if self.is_saudi_gtpl:
        if not self.etimad_tender_no:
            raise ValidationError(_("Etimad Tender Number is mandatory under Saudi GTPL."))
        if not self.is_bid_bond_valid:
            raise ValidationError(_(
                "GTPL Article 36 Violation: Initial Guarantee (Bid Bond) must be strictly between 1.0%% and 2.0%% "
                "of the total submitted bid price. Current percentage: %.2f%%."
            ) % self.bid_bond_pct)
        if not self.lcgpa_mandatory_list_pledge:
            raise ValidationError(_("Contractor must formally pledge adherence to LCGPA Mandatory National Products List."))
    return super().action_approve_bid()
```

### 2. Third-Party Safety Inspection & Equipment Readiness in `construction_equipment`

Extend `construction.equipment` and `hr.employee` with TÜV/BV/SASO inspection tracking, crane load testing, site stickers, and operator driving licenses:

```python
# Safety Inspection Validity Compute
@api.depends('is_saudi_safety_regulated', 'inspection_cert_no', 'inspection_expiry')
def _compute_safety_inspection_valid(self) -> None:
    today = fields.Date.context_today(self)
    for rec in self:
        if not rec.is_saudi_safety_regulated:
            rec.is_inspection_valid = True
        elif rec.inspection_cert_no and rec.inspection_expiry and rec.inspection_expiry >= today:
            rec.is_inspection_valid = True
        else:
            rec.is_inspection_valid = False

# Deployment Gate
def _check_saudi_safety_readiness(self) -> None:
    self.ensure_one()
    if not self.is_saudi_safety_regulated:
        return
    today = fields.Date.context_today(self)
    if not self.inspection_cert_no or not self.inspection_expiry or self.inspection_expiry < today:
        raise UserError(_(
            "Cannot deploy equipment '%s' (In Use): Third-Party Safety Inspection certificate is expired or missing. "
            "Saudi OSHA / Civil Defense regulations require a valid inspection (TÜV/BV/SGS/SASO)."
        ) % self.name)
    if self.category == 'crane' and not self.lifting_gear_tested:
        raise UserError(_("Cannot deploy crane '%s': Lifting Gear proof load test certification (SWL) is missing.") % self.name)
    if self.operator_id and not self.operator_id.is_heavy_license_valid:
        raise UserError(_("Cannot deploy equipment '%s': Assigned operator does not hold a valid heavy driving license.") % self.name)

def action_set_in_use(self) -> None:
    for rec in self:
        rec._check_saudi_safety_readiness()
    self.write({'state': 'in_use'})
```

---

## ⚠️ Pitfalls

1. **Test Suite Regressions via Premature Global Enforcement:** Do NOT hardcode `is_saudi_safety_regulated = True` as a static field default. Doing so breaks existing test suites (e.g. `test_equipment_usage_post.py`) and non-Saudi companies where third-party certificates are not maintained. Instead, default to `False`, apply `@api.onchange` in form views for Saudi companies, and enable explicitly in safety-regulated scenarios.
2. **Cranes vs Other Plant:** Never treat cranes like regular earthmoving machinery. Cranes strictly require Proof Load Testing for their hoisting mechanisms, wire ropes, and shackles in addition to regular vehicular safety.
3. **Usage Logs Past Inspection Expiration:** Site engineers often attempt to log hours after inspection stickers have expired. Enforce `@api.constrains('equipment_id', 'date')` on usage logs so historical data integrity is preserved while retroactive post-expiration logging is blocked.
4. **Bid Bond Validity Date Windows:** In Saudi GTPL, a bank guarantee letter expiring prior to technical/financial envelopes opening will disqualify the bid. Track `bid_bond_expiry_date` alongside the monetary amount.

---

## Verification

Run automated test suite:
```bash
python3 -m unittest construction_equipment.tests.test_saudi_equipment_safety
```

Expected result: All 5 safety compliance test cases pass cleanly without errors.

---

## References

- Saudi Government Tender and Procurement Law (نظام المنافسات والمشتريات الحكومية) - Royal Decree No. (M/128), Article 36 (Initial Guarantees) & Article 59 (Local Content).
- Local Content and Government Procurement Authority (LCGPA): [https://lcgpa.gov.sa](https://lcgpa.gov.sa)
- Saudi Building Code SBC 201 & SBC 801 (Safety during Construction).
- SASO Technical Regulations for Heavy Machinery and Lifting Equipment.
- Related file: `Best Practices/saudi-gtpl-bank-guarantees-advance-amortization.md`
