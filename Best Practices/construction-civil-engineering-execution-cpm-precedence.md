# Civil Engineering Execution Precedence & Fast-Tracking CPM in Construction Demonstrations

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `boq`, `work-order`, `cpm`, `civil-engineering`, `fast-tracking`, `data-seeding`, `precedence`

---

## Problem

When seeding or executing sample construction data (Work Orders `project.work.order` and Subcontractor Invoices `contract.subcontractor.invoice`), an automated script or careless distribution may execute all BOQ items simultaneously (e.g. 40% across all 30 items). This produces an impossible physical sequence on site:
- Installing porcelain tiles, marble flooring, interior acrylic paint, wood doors, and gypsum suspended ceilings while excavation is only at 80% and the concrete raft foundation is only at 5.4%.
- Installing elevators in an unfinished concrete shaft.
- Applying inverted roof waterproofing while the building has only reached the 5th floor.

When presented to engineering consultants, contractors, or executive clients, this completely discredits the software demonstration.

## Root Cause

Blindly distributing execution percentages across all BOQ rows uniformly ignores the Critical Path Method (CPM), construction sequence logic, and fast-tracking prerequisites governed by FIDIC and civil site engineering standards.

## Solution ✅

Follow the realistic 6-phase Fast-Tracking Construction Sequence:

### Phase 1: Substructure (الأعمال الترابية والأساسات) -> 100.0% Complete
Before any superstructure can reach multi-story height:
1. Site Mobilization & Temporary Fences: 100%
2. Mechanical Earth Excavation: 100%
3. Secant / Contiguous Shoring Piles: 100%
4. Soil Replacement & Compaction: 100%
5. Plain Blinding Concrete: 100%
6. Foundation Waterproofing & Protection: 100%
7. Reinforced Concrete Raft Foundation: 100%
8. Reinforced Concrete Retaining Walls: 100%

### Phase 2: Superstructure Concrete (الهيكل الخرساني للأدوار المتكررة) -> 50% - 60%
- Columns and Shear Walls: 60% (e.g., floors Basement to 6th floor poured).
- Flat Slabs: 60%.
- Stairs: 60%.
- **Roof Parapet & Upper Water Tank:** **0.0%** (MUST remain 0% until the top roof slab is cast).

### Phase 3: Masonry (أعمال المباني بالأدوار السفلية المصبوبة) -> 25% - 40%
- Solid Cement Blocks in Basements & Wet Areas: 40%.
- Hollow Clay Bricks on Ground & First Floors: 25%.
- Upper floors under casting: 0%.

### Phase 4: MEP 1st Fix (التأسيسات الكهروميكانيكية بالبلاطات المصبوبة والبدرومات) -> 10% - 20%
- Water Supply sleeves & risers: 20%.
- Drainage sleeves & underground pipes: 20%.
- Firefighting pipe mains in basements: 20%.
- Main electrical cable trays in basements: 15%.
- Slab embedded lighting conduits: 20%.
- Light current conduits: 15%.
- Central HVAC ductwork in basements: 10%.
- **Passenger Elevators:** **0.0%** (Elevator machinery and rails cannot be installed until the shaft is cast to the top machine room and fully weatherproofed).

### Phase 5: Rough Finishes (بياض المحارة بالأدوار المنتهية مبانيها) -> 15%
- Internal Cement Plaster: 15% (limited to basements and ground floor walls).

### Phase 6: Final Finishes & Roof Waterproofing (التشطيبات النهائية) -> 0.0% (Draft / Not Started)
Must remain at **0.0%** until plaster and wet trades are completed and the structure is fully topped off:
- Porcelain Flooring: 0.0%
- Marble Cladding & Treads: 0.0%
- Acrylic Interior Paint: 0.0%
- Gypsum Board False Ceilings: 0.0%
- Wooden Doors: 0.0%
- Structural Glazing Curtain Wall: 0.0%
- Inverted Roof Waterproofing: 0.0%

## ⚠️ Pitfalls

- **Draft Work Orders:** Moving a work order to `draft` automatically sets `is_cost_confirmed = False` across all its labor, equipment, and material lines, ensuring zero premature actual costs are booked to the BOQ item.
- **Subcontractor Billing:** Always adjust `current_qty` to match physical progress (e.g. 0.0 for elevator installations) and recompute invoice financials.
- **Hierarchical BOQ Roll-up:** Always call `_compute_qty_executed()`, `_compute_actuals()`, and `_compute_progress_from_qty()` from bottom leaves to root items to ensure accurate project progress and EVM metrics.

## Verification

Run verification in Odoo shell:
```python
boqs = env['project.boq.item'].search([('project_id', '=', proj.id), ('parent_id', '=', False)], order='sequence, id')
for b in boqs:
    print(f'{b.code:<12} | Qty: {b.quantity:8.1f} | Exec: {b.qty_executed:8.1f} | Prog: {b.progress_percentage:5.1f}% | Cost: {b.actual_cost:12.2f}')
```
Verify that all Substructure items are at 100%, Superstructure at 60%, Roof at 0%, Masonry at 25-40%, MEP at 10-20%, and all Finishes at 0.0%.
