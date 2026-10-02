# Construction Seeding & API Field Pitfalls: DCC Disciplines, Concrete Crushing Load, and EOT Claims

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-23                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `seeding`, `dcc`, `qc`, `concrete`, `claims`, `eot`, `orm`

---

## Problem

When writing seed data, test cases, or API integrations across the construction suite (`construction_dcc`, `construction_qc_inspection`, `construction_concrete_bbs`, `construction_claims_eot`), developers encounter three frequent ORM exceptions:

1. **DCC Discipline Selection Mismatch:**
   ```
   ValueError: Wrong value for dcc.submittal.discipline: 'structural'
   ```
2. **Concrete Cube Strength Ignored:**
   Passing `'strength_mpa': 33.5` into `construction.concrete.cube.line` does not set the cube compressive strength, resulting in 0.0 MPa and unintended test evaluations.
3. **Claim Record Field Invalidation:**
   ```
   ValueError: Invalid field 'claimed_cost' on model 'claim.record'
   ```

---

## Root Cause

1. **Standardized Uppercase Discipline Codes:**
   `construction_dcc` models (`dcc.submittal`, `dcc.rfi`, `dcc.document`, `dcc.distribution.matrix`) import `DISCIPLINE_SELECTION` from `dcc_codes.py`. Selection keys are capitalized abbreviations (`'STR'`, `'CIV'`, `'MEC'`, `'ELE'`, `'ARCH'`, `'PLB'`, `'HVAC'`, `'INST'`, `'GEN'`), not full lowercase English words (`'structural'`, `'mechanical'`).
2. **Field Physics & Testing Machine Simulation:**
   In laboratory compression testing, universal testing machines record the ultimate crushing load in kilonewtons ($kN$). In `construction.concrete.cube.line`, `strength_mpa` is a read-only computed field:
   $$\text{strength\_mpa} = \frac{\text{crushing\_load\_kn} \times 1000}{\text{surface\_area\_mm2}}$$
   For standard 150mm concrete cubes ($150 \times 150 = 22,500 \text{ mm}^2$):
   $$\text{crushing\_load\_kn} = \text{strength\_mpa} \times 22.5$$
   Additionally, cube specimen lines are stored under `line_ids` (One2many to `construction.concrete.cube.line`), not `specimen_ids`.
3. **Claims & Statutory Notice Schema:**
   `claim.record` defines:
   - `event_date`: Required date starting the 28-day notice period clock.
   - `claimed_amount`: Monetary field tracking financial claim exposure (not `claimed_cost`).
   - `status`: Selection lifecycle field (`'draft'`, `'notice_served'`, `'particulars_submitted'`, `'under_assessment'`, `'determined'`, `'closed'`) instead of `state`.

---

## Solution ✅

When creating records programmatically, adhere strictly to model field definitions:

```python
# 1. DCC Submittal & RFI (Use Uppercase Discipline Codes)
env['dcc.submittal'].create({
    'project_id': project.id,
    'title': 'Structural Shop Drawings - Raft Foundation',
    'submittal_type': 'shop_drawing',
    'discipline': 'STR',  # 'STR', 'MEC', 'ARCH', 'ELE', 'CIV'
    'recipient_party': 'consultant',
    'consultant_sla_days': 14,
    'state': 'submitted',
})

# 2. Concrete Cube Compressive Strength (crushing_load_kn on line_ids)
# Desired 33.5 MPa on a 150mm cube -> crushing_load_kn = 33.5 * 22.5 = 753.75 kN
env['construction.concrete.cube'].create({
    'project_id': project.id,
    'pour_id': pour.id,
    'test_age_days': '28',
    'specified_strength_mpa': 40.0,
    'specimen_shape': 'cube_150',
    'line_ids': [
        (0, 0, {'specimen_number': 1, 'crushing_load_kn': 753.75}),
        (0, 0, {'specimen_number': 2, 'crushing_load_kn': 753.75}),
        (0, 0, {'specimen_number': 3, 'crushing_load_kn': 753.75}),
    ],
})

# 3. EOT Claim Record (Required event_date, claimed_amount, status)
env['claim.record'].create({
    'project_id': project.id,
    'title': 'Extension of Time Claim No. 01',
    'claim_type': 'cost_and_time',
    'is_saudi_gtpl_claim': True,
    'gtpl_statutory_basis': 'delayed_site_handover',
    'claimed_days': 11,
    'claimed_amount': 125000.0,
    'event_date': '2025-05-01',  # Required
    'notice_date': '2025-05-10',
    'status': 'draft',           # 'status', not 'state'
})
```

---

## ⚠️ Pitfalls

- **Do NOT pass `strength_mpa` directly in cube line creation:** The ORM compute method recalculates and overwrites it to `0.0` if `crushing_load_kn` is not supplied.
- **DCC Numbering Sequences:** Sequences are parameterized by discipline code; using unmapped discipline keys breaks sequence resolution during auto-numbering.
- **Multi-Company Bank Guarantees:** `construction.bank.guarantee` requires both `project_id` and `contract_id` to be resolved; never create it before initializing the project.

---

## Verification

Run the seed or test script in the Odoo shell:
```bash
odoo-bin shell -c odoo.conf -d db_name --no-http < scratch/seed_turnkey_project_showcase.py
```
Confirm all 18 lifecycle phases execute without `ValueError` or `KeyError`.
