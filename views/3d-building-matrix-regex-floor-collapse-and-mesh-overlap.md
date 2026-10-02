# 3D Building Matrix: Regex Floor Key Collapse & Spatial Mesh Overlap

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `owl`, `threejs`, `webgl`, `3d`, `digital-twin`, `realestate`, `bim`, `regex`

---

## Problem

In 3D Building Visualizers and Digital Twins for real estate projects (e.g., Three.js / WebGL client actions in Odoo), all buildings across different projects display as a flat single-story building (1 floor) with only 2 visible apartments, despite having 10, 15, or 20 units in the database.

Furthermore, floating unit number badges on 3D meshes show the project code prefix (e.g. `010`) instead of the actual apartment number (e.g. `101`, `203`), and units on the same level overlap directly on top of each other (Z-fighting / visual collision).

```python
# Symptom in RPC return value:
data['floors'] -> [{'level': 1, 'label': '0', 'count': 20}]  # Only 1 floor generated!
data['units'] -> 20 units all assigned to floor 1 with overlapping coordinates
```

## Root Cause

1. **Naive Regex Grouping on Unit Codes:**
   When units do not have explicit `floor` values in the database, fallback logic attempted to extract digits using:
   ```python
   digits = re.findall(r'\d+', u.name or '')
   if digits and len(digits[0]) >= 3:
       f_key = digits[0][0]
   ```
   For standardized unit codes like `U-010-01` through `U-010-20`:
   - `digits` was `['010', '01']`.
   - `digits[0]` is `'010'` (the project code).
   - `digits[0][0]` is `'0'`.
   Every single unit was assigned to floor key `'0'`, collapsing all 20 units into a single floor!

2. **Badge Short Number Indexing:**
   The badge display logic used `short_num = digits[0]`, rendering `"010"` on every apartment's floating badge instead of `digits[-1]` (`"01"`, `"02"`, ...).

3. **Modulo Slot Overlap in 3D Space:**
   On the frontend / 3D generator, slot assignment used `slot = idx % 4`. When 20 units were lumped onto 1 floor, units 0, 4, 8, 12, 16 occupied the exact same `(x, y, z)` coordinates, overlapping completely. From the default camera angle, only 2 front apartments were visible.

## Solution ✅

1. **Robust Architectural Floor Auto-Distribution:**
   In the backend 3D data provider (`get_project_units_3d`):
   - Check if the project already has an established multi-floor plan (`has_multi_floor_plan = len(set(valid_floors)) > 1`).
   - If not, distribute units sequentially into standard architectural floors (4 apartments per floor, or 2 for small projects):
     ```python
     total_units = len(units)
     units_per_floor = 4 if total_units > 8 else (2 if total_units > 2 else 1)
     
     digits = re.findall(r'\d+', u.name or '')
     if digits:
         unit_num = int(digits[-1])
         if unit_num >= 100:
             # E.g. "A-101" -> Floor 1, "204" -> Floor 2
             f_key = str(unit_num // 100)
         else:
             # E.g. "U-010-01" .. "U-010-20" -> Floor 1..5
             f_key = str(((unit_num - 1) // units_per_floor) + 1)
     else:
         f_key = str((idx // units_per_floor) + 1)
     ```

2. **Natural Vertical Floor Sorting:**
   Ensure Basement, Ground, Mezzanine, numeric floors, and Penthouse sort vertically from bottom to top:
   ```python
   def natural_floor_sort_key(k: str) -> float:
       k_lower = str(k).lower().strip()
       if any(w in k_lower for w in ['basement', 'بدروم', 'قبو']):
           return -2.0
       if any(w in k_lower for w in ['ground', 'أرضي', 'ارضي', 'g', 'gf']):
           return 0.0
       if any(w in k_lower for w in ['mezzanine', 'ميزانين', 'm']):
           return 0.5
       digits = re.findall(r'\d+', str(k))
       if digits:
           return float(digits[0])
       if any(w in k_lower for w in ['penthouse', 'بنتهاوس', 'روف', 'roof']):
           return 999.0
       return 500.0
   ```

3. **Dynamic Multi-Unit Placement Grid:**
   Prevent 3D mesh overlap by handling 1-unit (royal suite), 2-unit (luxury duplexes), 3-unit, 4-unit quadrants, and dynamic multi-column grids for floors with > 4 units.

4. **Self-Healing DB Backfill:**
   When generating 3D data, write the resolved `f_key` back to `u.floor` if empty, ensuring consistency across backend tree/form views, contracts, and 3D scenes.

## ⚠️ Pitfalls

- Never assume `digits[0]` is the apartment number when records follow enterprise naming conventions (`PREFIX-PROJECT-UNIT`). Always inspect `digits[-1]` for sequential unit numbers.
- Avoid hardcoding fixed heights (`floorBaseHeights = {1: 0.2, 2: 2.2}`) without a fallback linear formula `(0.2 + (level - 1) * 2.0)` to safely support 10+ floor towers.
- In Three.js OrbitControls, dynamically set `controls.target.set(0, totalHeight / 2, 0)` and camera distance to adapt to buildings with different floor counts.

## Verification

Run automated test verifying multi-floor distribution and non-overlapping coordinates:

```bash
python3 odoo-bin -c odoo.conf -d odoo_test --test-enable --test-tags=construction_realestate_3d --stop-after-init
```

Check RPC output across projects:
```python
data = env['realestate.unit'].get_project_units_3d(project_id)
assert len(data['floors']) > 1
assert all(len(f_units) <= 4 for f_units in floor_groups)
```

## References

- Related: `views/owl-client-action-dict-key-casing-silent-ui-hide.md`
- Module: `construction_realestate_3d`
