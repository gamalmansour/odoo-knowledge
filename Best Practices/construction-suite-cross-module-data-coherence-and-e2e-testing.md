# Construction Suite Cross-Module Data Coherence & End-to-End Testing

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `end-to-end`, `data-integrity`, `cross-module`, `seeding`, `boq`, `wbs`, `hse`, `subcontractor`, `qaqc`

---

## Problem

In multi-module ERP enterprise suites (such as a 33-module Construction ERP suite comprising Tendering, Subcontracting, Equipment, HSE, QA/QC, Site Supervision, DCC, Claims, and Real Estate), developers or automated agents frequently perform "silo testing" — testing only the single screen or module being developed. 

When a QA engineer, tech lead, or client navigates through the integrated solution:
1. Operational screens like **HSE Incidents**, **Work Permits (PTW)**, **Material Requisitions**, or **QA/QC NCRs** appear completely empty for the active project.
2. Cross-module data is inconsistent (e.g., Subcontract valuations with no backcharges, or Real Estate 3D unit matrix showing zero cost because project actual costing was never calculated and linked to the units).
3. Test scripts fail due to subtle ORM design constraints (e.g., `project.labor.record.project_id` being a stored computed field that depends on `boq_target_id` or `work_order_id`, so writing `project_id` directly without the parent BOQ item causes `project_id` to be silently wiped or set to False on recompute).

## Root Cause

1. **Silo Feature Development:** Changes are verified only on the target model's view, neglecting downstream and upstream lifecycle dependencies.
2. **Model Polymorphism & Aliasing:** Standard Odoo uses `project.project` for generic tasks, while vertical construction suites use a dedicated model `construction.project`. Passing a generic `project.project` ID to construction models causes silent `MissingError` or empty recordsets.
3. **Indirect Compute Hierarchies:** Operational lines (such as labor logs and equipment logs) compute their analytical and project ties from parent Cost Codes, BOQ Items, or Work Orders rather than accepting direct writes.

## Solution ✅

Follow a **Single-Narrative End-to-End Master Seed Pipeline** where every project in the database has full operational depth across the entire 21-point construction lifecycle:

### Master Lifecycle Sequence:
1. **Tender & BOQ:** `project.boq.item` (Structural concrete, MEP, Architectural)
2. **WBS Nodes:** `project.wbs` (Hierarchical breakdown levels)
3. **Cost Codes:** `construction.cost.code` (Standard CSI/MasterFormat codes)
4. **Subcontractor Lifecycle:** 
   - `contract.subcontractor` (Primary subcontract agreement)
   - `contract.subcontractor.invoice` (Subcontract IPC/Valuation)
   - `subcontractor.evaluation` (Performance scorecard with scores 1 to 5)
   - `construction.backcharge` (Contra-charges for site cleanup/damage)
5. **Site Procurement & Resources:**
   - `construction.material.requisition` (Approved & received site MRs)
   - `project.labor.record` (Linked to `boq_target_id` so `project_id` computes reliably)
   - `construction.equipment` (Heavy equipment with active allocation)
6. **HSE Governance:**
   - `hse.incident` (Near-miss, First aid, and Lost time incidents)
   - `hse.permit` (Working at height, Hot work, Confined space PTWs)
   - `hse.inspection` (Site audits and scaffolding inspections)
   - `hse.toolbox.talk` (Daily safety pre-start talks)
7. **QA/QC Compliance:**
   - `qc.inspection.request` (Work and material inspection requests with status)
   - `qc.ncr` (Non-conformance reports with corrective action disposition)
8. **Project Supervision & DCC:**
   - `construction.meeting` (Site coordination MOMs with HTML minutes)
   - `dcc.rfi` (Requests for information with consultant SLA tracking)
   - `construction.risk` (Risk register with probability, impact, mitigation)
   - `claim.record` (Contractor extension of time & cost claims)
   - `construction.site.photo` (Geotagged site progress photos with base64 images)
9. **Real Estate Integration:**
   - `realestate.unit` (Unit matrix with areas, actual cost sync, and 3D status)

## ⚠️ Pitfalls

- **Do NOT pass `project.project` ID to `construction.project` Many2one fields.** Always check `field.comodel_name` on the model before seeding.
- **Computed Fields Without Inverse:** Setting `project_id` on `project.labor.record` directly will be overwritten by `_compute_project_id()`. Always supply `boq_target_id` or `work_order_id`.
- **Scorecard Range Validation:** `subcontractor.evaluation` strictly enforces scores between 1 and 5 (`score_quality`, `score_safety`, etc.). Passing percentages (e.g., 90) will trigger a `ValidationError`.

## Verification

Run an automated 21-point cross-module audit script verifying that count > 0 for all checkpoints on the target project.

## References

- Related: `Best Practices/saudi-construction-labor-saudization-and-sbc-ptw.md`
- Related: `Best Practices/saudi-sbc-qaqc-concrete-testing-and-decennial-warranty-dlp.md`
