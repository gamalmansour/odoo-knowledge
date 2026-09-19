# Real Estate Unit Cost Allocation & Off-Plan Zero Cost Trap

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `realestate`, `construction`, `cost-allocation`, `wafi`, `off-plan`, `projected-margin`, `3d`, `digital-twin`

---

## Problem

In integrated Construction and Real Estate Development solutions (e.g., residential towers, off-plan / Wafi developments), unit detail cards, 3D Building Matrix visualizers, and financial reports display:
- **Unit Allocated Cost:** `0.0 SAR`
- **Projected Margin:** `1,200,000 SAR` (100% of list price)

This creates serious confusion for sales directors, investment stakeholders, and prospective buyers inspecting digital twins, who see impossible 100% margins and zero construction cost.

---

## Root Cause

1. **Batch Accounting Closing vs. Real-time Compute:**
   In enterprise construction ERPs, cost allocation (`allocated_cost`) is intentionally designed as an event-driven batch financial distribution (`action_allocate_cost()` or allocation wizards). It is not an automatic recompute on every raw warehouse issue or timesheet to prevent constant shifting of unit costs.
2. **The Off-Plan / Under-Construction Void:**
   In modern real estate development (especially Saudi Wafi off-plan sales), units are marketed and sold *before* or *during* construction. At early phases, actual incurred expenditure (`total_cost_actual`) is zero or very small.
   When the allocation engine strictly depends on `rec.total_cost_actual`, it distributes `0.0` across units, producing `allocated_cost = 0.0` and `projected_margin = list_price`.
3. **Visualization / Digital Twin Missing Fallback:**
   Read-only data endpoints (like `get_project_units_3d`) simply extract `u.allocated_cost or 0.0`. If manual allocation has not yet been executed on the project, the visualizer naively shows zero cost.

---

## Solution ✅

### 1. Dual Cost Base in Allocation Logic (Actuals with Budget Fallback)
In `construction.project` cost allocation routines, use actual cost if incurred; otherwise, fall back to the approved construction target budget (`total_budget`):

```python
total_cost = rec.total_cost_actual if (rec.total_cost_actual and rec.total_cost_actual > 0) else (rec.total_budget or 0.0)
```

### 2. Intelligent Auto-Allocation & Fallback in Digital Twin (`get_project_units_3d`)
When fetching unit twin data, check if units are unallocated. If so, dynamically compute pro-rata allocation from the cost base and persist it non-blockingly:

```python
total_allocated = sum(u.allocated_cost for u in units)
cost_base = target_project.total_cost_actual if (target_project.total_cost_actual and target_project.total_cost_actual > 0) else (target_project.total_budget or 0.0)
method = getattr(target_project, 'cost_allocation_method', 'area') or 'area'

if units and cost_base > 0.0 and total_allocated <= 0.0:
    active_units = units.filtered(lambda u: u.state not in ('sold', 'handed_over')) or units
    weight_base = sum(u.area_sqm for u in active_units) if method == 'area' else sum(u.list_price for u in active_units)
    if not weight_base:
        method = 'equal'
        weight_base = float(len(active_units))

    for unit in active_units:
        w = unit.area_sqm if method == 'area' else (unit.list_price if method == 'price' else 1.0)
        unit_alloc = round(cost_base * (w / weight_base), 2)
        try:
            unit.sudo().write({'allocated_cost': unit_alloc})
        except Exception:
            pass  # Safe non-blocking write for concurrent viewers
```

### 3. Strict State-Based Cost Freezing (IFRS 15 Compliance)
Always exclude sold and handed-over units from absorbing subsequent construction cost variations:

```python
frozen_units = all_units.filtered(lambda u: u.state in ['sold', 'handed_over'])
active_units = all_units - frozen_units
frozen_cost = sum(u.allocated_cost for u in frozen_units)
cost_to_allocate = total_cost - frozen_cost
```

---

## ⚠️ Pitfalls

1. **Writing inside Read RPC Handlers:**
   Always wrap auto-allocation database writes in `try ... except Exception: pass`. If two users open the 3D visualizer simultaneously, concurrent row locking could otherwise throw a PostgreSQL serialization error.
2. **Zero Division on Draft Units:**
   If units have 0.0 m² area or 0.0 price, multi-tier fallback (area → price → unit count) is mandatory to prevent `ZeroDivisionError`.
3. **Odoo Computed Field Assignment Trap:**
   `total_budget` on `construction.project` is a computed field stored from `project.boq.item` records. Setting `'total_budget': 4000000.0` in `project.create()` is silently dropped; test fixtures must create a BOQ item to establish the budget.
