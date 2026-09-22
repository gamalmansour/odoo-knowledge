# Saudi Building Code QA/QC & Statutory Decennial Warranty DLP Compliance

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-arabia`, `sbc`, `qaqc`, `concrete-testing`, `slump`, `compressive-strength`, `soil-compaction`, `dlp`, `decennial-warranty`, `civil-transactions-law-470`, `idi`, `balady`

---

## Problem

Construction contractors and engineering supervisors operating in the Kingdom of Saudi Arabia face catastrophic structural failures, legal liability, and multimillion-riyal contractual disputes due to two major gaps:

1. **Saudi Building Code (SBC) & Balady QA/QC Non-Compliance**:
   - Pouring structural concrete without verifying the pre-pour consultant approval card, batch plant ticket, or slump tolerance (typically 75mm - 175mm per SBC 304).
   - Approving structural elements when 7-day lab breaks fall below 65% or 28-day cylinder tests fail design compressive strength ($f'_c < f'_{c,\text{specified}}$).
   - Proceeding with backfilling and subbase layers without third-party lab proctor compaction results meeting the mandatory $\ge 95\%$ maximum dry density (SBC 303).
   - Closing Non-Conformance Reports (NCRs) without recording specific Balady violation citations or SBC clauses, leading to municipal fines during Balady field audits.

2. **Premature Handover & Decennial Liability Exposure (Civil Transactions Law Art. 470 & IDI)**:
   - Releasing the contractor's final retention tranche (typically 5%) based solely on calendar DLP expiry, without obtaining the signed tripartite Final Handover Certificate (`محضر الاستلام النهائي`) or the Civil Defense final safety clearance (`سلامة الدفاع المدني`).
   - Failure to record statutory 10-Year Decennial Warranties for structural elements and thermal/waterproofing insulation as mandated by Article 470 of the Saudi Civil Transactions Law (نظام المعاملات المدنية - المرسوم الملكي م/191).
   - Missing mandatory Inherent Defects Insurance (IDI - تأمين العيوب الخفية الإلزامي) policy registration approved by SAMA / the Insurance Authority under Council of Ministers Resolution No. 509.

---

## Root Cause

Generic ERP systems treat Quality Control inspection requests (WIR/MIR) and DLP warranty records as passive administrative forms:
- Test records accept arbitrary qualitative values ("Good", "Approved") without verifying numerical strength ($f'_c$), slump displacement, or compaction percentages against building code tolerances.
- DLP modules trigger retention release workflows automatically when the calendar warranty duration lapses, ignoring statutory sign-offs and municipal safety clearances.
- Contracts mistakenly assume that the issuance of the final completion certificate relieves the contractor and engineer of structural liability, contrary to public order statutory decennial liability.

---

## Solution ✅

Implement automated Saudi regulatory compliance engines across both `construction_qaqc` and `construction_dlp`:

### 1. SBC QA/QC Inspection & Lab Testing Engine (`construction_qaqc`)

Enforce structural concrete testing and geotechnical compaction parameters directly on `qc.inspection.request`:

```python
@api.depends('strength_28days_mpa', 'strength_7days_mpa', 'specified_fc')
def _compute_concrete_test_result(self):
    for rec in self:
        if not rec.specified_fc or rec.specified_fc <= 0:
            rec.concrete_test_result = 'pending'
            continue
        if rec.strength_28days_mpa > 0:
            rec.concrete_test_result = 'pass' if rec.strength_28days_mpa >= rec.specified_fc else 'fail'
        elif rec.strength_7days_mpa > 0:
            # 7-day early indicator: typically requires >= 65% to 70% of 28-day design strength
            rec.concrete_test_result = 'pass' if rec.strength_7days_mpa >= (0.65 * rec.specified_fc) else 'fail'
        else:
            rec.concrete_test_result = 'pending'

@api.depends('proctor_density_pct')
def _compute_compaction_status(self):
    for rec in self:
        if not rec.is_soil_compaction:
            rec.compaction_status = 'pending'
        elif rec.proctor_density_pct >= 95.0:
            rec.compaction_status = 'pass'
        elif rec.proctor_density_pct > 0:
            rec.compaction_status = 'fail'
        else:
            rec.compaction_status = 'pending'
```

Strictly guard result recording in `action_record_result()`:
- Block recording if concrete test is `'fail'` (strength below design $f'_c$).
- Block recording if soil proctor compaction is `'fail'` ($< 95\%$).

### 2. Cost of Poor Quality (COPQ) & Master Checklist Templates Engine

1. **CBS Cost Code Tagging for COPQ Tracking**:
   - Link `qc.project.mixin` to `construction.cost.code` (`cost_code_id`).
   - Automatically propagate CBS codes from `qc.checklist.template` → `qc.inspection.request` → `qc.ncr`.
   - Aggregate financial non-conformance costs (`cost_of_quality`) by CBS division (e.g. Division 03 Concrete, Division 07 Waterproofing) so executives and project managers can track COPQ in real time.

2. **Standard Engineering Checklist Templates & 1-Click ITP Generation**:
   - Pre-load standard reusable checklist templates (`qc.checklist.template`) derived from proven megaproject quality control procedures:
     * Pre-Pour Concrete & Rebar Inspection (Formwork, cover spacers, rebar spacing, embedments, DPM).
     * Concrete Pouring & Quality Testing (Batch tickets, transit time, fresh concrete temp, slump, 6-specimen sampling, wet curing).
     * Block Works & Masonry (Alignment, plumbness, mortar mix 1:3, wall ties, lintel bearings ≥ 200mm).
     * Protected Membrane Roofing & Waterproofing (Foam concrete slopes ≥1.5%, chamfers, primer, 4mm torching, 100mm overlaps, 48-72h water flood test).
     * Plumbing Water Supply Hydrostatic Test (PPR PN16/20, air bleeding, 10-15 bar pressure hold, zero drop).
     * Drainage Network Gravity Flow & Leakage Test (UPVC Class 4/5, 1.5-2.0% gradient, rubber plug water test, ball flow test).
     * HVAC Ductwork Installation & SMACNA Leakage Test (Gauge thickness, UL fire dampers, trapeze hangers, elastomeric sealant, CFM leakage measurement).
     * Electrical Conduits, Wiring & Megger Test (High-impact UPVC, box FFL heights, phase color coding, PE continuity, 500V/1000V DC Megger ≥ 100 MΩ).
     * Earthworks Subgrade & Layer Compaction (A-1-a material, lifts ≤ 300mm, OMC ±2%, Modified Proctor ≥ 95% per SBC 303).
     * Survey Works & Setting Out (Permanent TBMs, boundary setbacks, formation levels, column centerlines).
   - Add `action_load_from_template()` on `qc.itp` to instantly generate project-specific ITP lines from master checklist templates with 1 click.

3. **Material Inspection Request (MIR) Gate**:
   - Dedicated MIR fields: `material_qty_delivered`, `material_uom_id`, `material_supplier_id`, `material_delivery_note_ref`, `has_mill_certificate`, and `material_storage_location`.
   - Prevent installation of received materials on site until MIR is formally approved by the consultant.

### 3. Saudi Decennial Warranty & Handover Safety Gates (`construction_dlp`)

#### A. Statutory Warranty Register (`dlp.warranty`)
- Configure mandatory warranty types with automated statutory durations:
  - `decennial_structural`: 120 Months (10 Years).
  - `decennial_waterproofing`: 120 Months (10 Years).
  - `idi_insurance`: 120 Months (10 Years).
  - `mep_finish`: 12 Months (1 Year).
- Track SAMA-licensed insurance provider, IDI policy number, and accredited Technical Inspection Service (TIS) entity.

#### B. Final Completion & Retention Release Gates (`dlp.period`)
Strictly block `action_final_completion()` unless statutory gates are cleared:
```python
# Saudi Statutory Final Handover Gate
if not self.is_final_handover_signed:
    raise UserError(_("Saudi Statutory Gate: Final Handover Certificate (محضر الاستلام النهائي) must be signed by the Client/Consultant before finalizing DLP and releasing retention."))

# Civil Defense Safety Gate
if not self.civil_defense_final_clearance:
    raise UserError(_("Civil Defense Safety Gate: Final Civil Defense safety & occupancy clearance must be verified before final project completion."))
```

---

## ⚠️ Pitfalls

1. **Unwaivability of Decennial Liability (نظام المعاملات المدنية المادة 470 فقرة 3)**:
   Any contractual clause attempting to waive, limit, or shorten the 10-year joint liability of the contractor and supervising engineer for structural collapse or stability defects is legally VOID under Saudi law. Never configure decennial warranties with durations under 120 months.
2. **Intermediate 7-Day vs 28-Day Strength Verification**:
   Concrete can be poured and inspected based on 7-day strength ($\ge 65\%$), but the element must not be subjected to design loads until the 28-day cylinder breaks confirm $f'_c \ge \text{specified } f'_c$.
3. **Soil Compaction Sample Representativeness**:
   Proctor density must be verified per layer (lift) not exceeding 300mm thickness. Testing the top surface of a multi-layer embankment invalidates the geotechnical pass.
4. **PO Translation Key Collisions**:
   In `i18n/ar.po`, avoid duplicate `msgid` occurrences between view headers and field labels. If strings match, merge references under a single `msgid`.

---

## Verification

1. **Python Syntax Verification**:
   ```bash
   python3 -m py_compile models/qc_inspection_request.py models/dlp_warranty.py models/dlp_period.py
   ```
2. **XML View and Report Validation**:
   ```bash
   python3 -c "import xml.etree.ElementTree as ET; ET.parse('views/dlp_warranty_views.xml')"
   ```
3. **Translation Integrity**:
   ```bash
   msgfmt -c -v i18n/ar.po -o /dev/null
   ```

---

## References

- Saudi Building Code (SBC 201 Architectural, SBC 301-304 Structural Concrete, SBC 801 Fire Prevention)
- Saudi Civil Transactions Law (نظام المعاملات المدنية - المرسوم الملكي رقم م/191 لسنة 1444هـ، المادة 470)
- SAMA / Insurance Authority Council of Ministers Resolution No. 509 (Inherent Defects Insurance IDI)
- Balady Municipal Inspection Guidelines (وزارة البلديات والإسكان)
- Related files:
  - `construction_qaqc/models/qc_inspection_request.py`
  - `construction_qaqc/models/qc_ncr.py`
  - `construction_dlp/models/dlp_warranty.py`
  - `construction_dlp/models/dlp_period.py`
  - `construction_dlp/models/dlp_period_final.py`
