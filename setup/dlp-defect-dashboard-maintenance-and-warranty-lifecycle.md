# DLP Defect Dashboard, Maintenance Visits, and Warranty Lifecycle

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `construction_dlp`, `dlp`, `defect-dashboard`, `maintenance-visits`, `warranties`, `kanban`, `search-filters`, `decennial-warranty`, `civil-defense`

---

## Problem

When navigating to **DLP & Warranty** in Odoo Construction Suite:
1. **Empty Screens Across the Entire DLP Module:**
   - **Defect Dashboard** (`menu_dlp_defects` / `action_dlp_defect_dashboard`): Opens a blank Kanban board with zero cards.
   - **Maintenance Visits** (`menu_dlp_maintenance` / `action_dlp_maintenance_visit`): Opens with zero scheduled or completed maintenance visits.
   - **DLP Periods** (`menu_dlp_periods` / `action_dlp_period`): Shows only 1 legacy record, giving no visibility across multiple ongoing projects.
2. **Default Filter Traps:**
   - **Defect Dashboard (`action_dlp_defect_dashboard`):** Sets context `{'search_default_filter_open': 1}`. The filter domain `[('state', 'in', ('open', 'in_progress', 'rectified', 'rejected'))]` correctly displays unresolved tickets, but hides `verified` and `closed` defects. If the database only contains closed tickets or zero tickets, the Kanban columns appear completely hollow.
   - **Maintenance Visits (`action_dlp_maintenance_visit`):** Defaults to `{'search_default_filter_planned': 1}`, which strictly limits records to `[('state', '=', 'planned')]`. Any visits in `done` or `missed` states are hidden by default, leading project engineers to assume past inspection logs were lost.
   - **DLP Periods (`action_dlp_period`):** Defaults to `{'search_default_filter_active': 1}`, displaying only records in `('active', 'in_final_inspection')`.
3. **Hard Model Constraint & Data Seeding Blockers:**
   - `dlp.period` enforces `@api.constrains('project_id', 'state')`: A project can only have ONE active DLP period at a time (`active` or `in_final_inspection`). Seeding scripts that attempt to create multiple active periods on the same project immediately crash with `ValidationError`.
   - `dlp.defect` and `dlp.maintenance.visit` inherit from `dlp.project.mixin`. If `project_id` is omitted in programmatic creation, it must safely resolve from `period_id.project_id`.

---

## Root Cause

1. **Missing Production-Grade Seed Data:** Standard demo records (`demo_dlp_periods.xml`, `demo_defects.xml`) depend on hardcoded XML IDs from synthetic demo modules that are omitted in real client databases (`hadhoud_demo`), leaving the post-handover DLP lifecycle unpopulated.
2. **Unbalanced Action State Traps:** Default search filters require records in specific lifecycle stages (`planned` for visits, `open` for defects, `active` for periods) to render meaningful dashboards upon initial navigation.
3. **Final Handover Gate Dependencies:** Transitioning DLP periods to `completed` requires zero open defects (`open_defect_count == 0`), signed final handover certificate, and civil defense clearance. Without proper stage distribution, test cases cannot simulate both active rectifications and successful closeouts.

---

## Solution ✅

### 1. Multi-Stage Realistic DLP Lifecycle Seeding

Seed DLP periods across distinct Egyptian megaprojects respecting the single active period constraint:

```python
# Project 3 (Rafah Reconstruction) - Active DLP
dlp_rafah = DlpPeriod.create({
    'project_id': p_rafah.id,
    'contract_id': c_rafah.id,
    'practical_completion_date': date(2026, 2, 15),
    'duration_months': 12,
    'state': 'active',
    'is_final_handover_signed': False,
    'civil_defense_final_clearance': True,
})

# Project 1 (Ismailia Logistics) - In Final Inspection
dlp_ismailia = DlpPeriod.create({
    'project_id': p_ismailia.id,
    'contract_id': c_ismailia.id,
    'practical_completion_date': date(2025, 9, 1),
    'duration_months': 12,
    'state': 'in_final_inspection',
    'is_final_handover_signed': True,
    'final_handover_cert_ref': 'FHC-SCZONE-2026-0042',
    'civil_defense_final_clearance': True,
})

# Project 4 (Monorail East Nile) - Completed DLP
dlp_monorail = DlpPeriod.create({
    'project_id': p_monorail.id,
    'contract_id': c_monorail.id,
    'practical_completion_date': date(2025, 1, 15),
    'duration_months': 12,
    'final_completion_date': date(2026, 1, 20),
    'state': 'completed',
    'is_final_handover_signed': True,
    'final_handover_cert_ref': 'FHC-NAT-MONORAIL-2026-001',
    'civil_defense_final_clearance': True,
})
```

### 2. Maintenance Visits Distribution Across States

Ensure visits include both `planned` (to satisfy default filter) and `done`/`missed` (to demonstrate inspection findings and defect linkages):

```python
# Planned Routine Visit (Matches default filter)
DlpVisit.create({
    'period_id': dlp_rafah.id,
    'project_id': p_rafah.id,
    'visit_type': 'scheduled',
    'planned_date': date(2026, 10, 15),
    'engineer_id': admin_user.id,
    'checklist_note': 'فحص أنظمة المصاعد ولوحات التوزيع الكهربائية بالمجاورة الرابعة',
    'state': 'planned',
})

# Completed Reactive Visit with Findings linked to Defect
done_visit = DlpVisit.create({
    'period_id': dlp_rafah.id,
    'project_id': p_rafah.id,
    'visit_type': 'scheduled',
    'planned_date': date(2026, 5, 15),
    'actual_date': date(2026, 5, 16),
    'engineer_id': admin_user.id,
    'checklist_note': 'معاينة عوازل الأسطح بعد اختبار الغمر',
    'findings': 'تم رصد نشع مائي خفيف حول مخارج تصريف مياه الأمطار',
    'state': 'done',
})
```

### 3. Defect Kanban Multi-Column Seeding

Populate defects across all disciplines (`architectural`, `electrical`, `civil`, `plumbing`, `mechanical`) and states (`open`, `in_progress`, `rectified`, `verified`, `closed`):

```python
# Critical Open Defect
DlpDefect.create({
    'title': 'عطل بلوحة التحكم الإلكترونية لمصعد عمارة 2',
    'period_id': dlp_rafah.id,
    'project_id': p_rafah.id,
    'discipline': 'electrical',
    'severity': 'critical',
    'source': 'client',
    'location': 'غرفة محركات المصعد - عمارة 2',
    'reported_date': date(2026, 10, 2),
    'target_date': date(2026, 10, 6),
    'state': 'open',
})

# High Severity In-Progress Defect linked to Visit
DlpDefect.create({
    'title': 'نشع مائي ورشح أسفل عزل الأسطح بالعمارة رقم 6',
    'period_id': dlp_rafah.id,
    'project_id': p_rafah.id,
    'discipline': 'architectural',
    'severity': 'high',
    'source': 'maintenance_visit',
    'visit_id': done_visit.id,
    'subcontractor_id': sub_rafah.id,
    'reported_date': date(2026, 5, 16),
    'target_date': date(2026, 5, 30),
    'state': 'in_progress',
})
```

### 4. Decennial & Inherent Defects Insurance (IDI) Register

Seed statutory warranties covering 10-year structural stability, waterproofing, and equipment warranties:

```python
DlpWarranty.create({
    'item_name': 'ضمان الهيكل الخرساني الإنشائي (10 سنوات)',
    'project_id': p_rafah.id,
    'warranty_type': 'decennial_structural',
    'duration_months': 120,
    'supplier_id': supplier_concrete.id,
    'start_date': date(2026, 2, 15),
    'state': 'active',
})
```

---

## ⚠️ Pitfalls to Avoid

1. **Violating Single Active DLP Constraint:**
   Never set more than one DLP period for the same project in `active` or `in_final_inspection` state; use `completed` or `closed` for earlier phases.
2. **Missing `planned` Maintenance Visits:**
   Because `action_dlp_maintenance_visit` defaults to `{'search_default_filter_planned': 1}`, seeding only past/completed visits will cause the screen to look empty upon first open. Always seed upcoming planned visits.
3. **Closing DLP Periods with Open Defects:**
   `dlp.period.action_final_completion()` blocks with `UserError` if `open_defect_count > 0`. Ensure defects are verified and closed before attempting final completion on closed periods.
4. **Saudi / Egyptian Statutory Gate Compliance:**
   When testing final completion on Saudi or regulated contracts, `is_final_handover_signed` and `civil_defense_final_clearance` must both be set to True.
