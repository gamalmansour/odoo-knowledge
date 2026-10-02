# Tiered Commission Target Achievement Audit and OWL Percentage Widget Factor Pitfall

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `commission`, `widget`, `percentage`, `owl`, `audit`, `formatters`, `snapshot`

---

## Problem

In commission engines with tiered policy matrices based on target achievement (e.g. `from_percentage` to `to_percentage`):
1. **Transient Calculation / Lack of Historical Audit Trail:** Target achievement % is computed dynamically in RAM during transaction confirmation to match a tier and compute the commission amount, but is not persisted on the generated commission lines (`commission.lines`). Financial reviewers and auditors see final commission numbers but cannot verify which tier or achievement percentage justified the payout without recalculating quarterly numbers manually.
2. **The 100x OWL Percentage Widget Pitfall:** When a developer adds a `Float` field to display the percentage and renders it with `widget="percentage"`, Odoo's OWL client formatter (`formatPercentage`) multiplies `value * 100` before appending `%`. If the calculation saves `85.0` (meaning 85%), the UI renders `8500%`, causing confusion and false audit alarms.
3. **Role-Specific Column Fragmentation (`personal` vs `cut`):** In supervisory hierarchies where agents earn personal commissions and managers earn override cuts, displaying `personal` directly in the line list leaves manager lines displaying `0.0`, even though a target achievement is shown.

---

## Root Cause

1. **Transient Variable Lifetime:** In typical Odoo models, `achievement = (sales / target) * 100` is used inside `_find_policy_line()` and discarded. Later quarterly sales additions alter the agent's target ratio, destroying historical proof of what the ratio was at the exact moment the deal was booked.
2. **Odoo Web Client Formatter Specification:** In `@web/views/fields/formatters.js`, `formatPercentage`:
   ```javascript
   export function formatPercentage(value, options = {}) {
       value = value || 0;
       const formatted = formatFloatNumber(value * 100, options);
       return `${formatted}${options.noSymbol ? "" : "%"}`;
   }
   ```
   Odoo expects percentage fields using `widget="percentage"` to store the decimal ratio ($0.85 = 85\%$, $1.0 = 100\%$, $1.25 = 125\%$).
3. **Column Mapping:** Separate fields `personal` and `cut` exist on the line, but standard views often only expose `personal`.

---

## Solution ✅

### 1. Store the Decimal Ratio with 4-Decimal Precision on the Line Model

In the line model inheriting `commission.lines`:
```python
class CommissionLines(models.Model):
    _inherit = 'commission.lines'

    achievement_percentage = fields.Float(
        string="Target Achievement",
        digits=(16, 4),
        help="Target achievement ratio at the time of commission calculation."
    )
```
> **Note on `digits=(16, 4)`:** Decimal percentages (e.g., $85.5\% \rightarrow 0.8550$) require at least 4 decimal places in the database so fractional achievement isn't truncated to integer percentages.

### 2. Safeguard Division by Zero & Store the Snapshot Ratio

In calculation methods:
```python
# 1) Calculate ratio safely
achievement = (total_sales / target) * 100.0 if target and target > 0 else 0.0

# 2) Save ratio (divided by 100) on the line during create()
commission_lines.create({
    'employee_id': agent.id,
    'position_id': agent_position.id,
    'sales_type': 'personal',
    'personal': commission_amount,
    'achievement_percentage': (achievement / 100.0) if achievement else 0.0,
})
```

### 3. Expose Unified Display Field & Percentage Widget in XML

In the list/tree view:
```xml
<field name="employee_id" readonly="1"/>
<field name="position_id" string="Job Position" readonly="1"/>
<field name="achievement_percentage" string="Target Achievement" widget="percentage" readonly="1"/>
<field name="commission_achieved" string="Current Commission" readonly="1"/>
<field name="actual_commission" string="Actual Commission" readonly="1"/>
```
> `commission_achieved` is a computed field: `personal if sales_type == 'personal' else (cut or personal)`.

---

## ⚠️ Pitfalls

- **Never pass 85.0 to `widget="percentage"`:** It will display `8500%`. Always pass `85.0 / 100.0 = 0.85`.
- **Avoid non-stored compute for historical ratios:** If `achievement_percentage` is a dynamic non-stored computed field, viewing a 6-month-old deal will show the employee's *current* quarter achievement instead of the achievement at the time the deal occurred. Always store it as a historical snapshot.
- **Ensure division-by-zero guards:** If an employee has no target or an empty goal tracker, guard with `if target and target > 0: ... else: 0.0` to avoid crashing document creation or approval.

---

## Verification

1. Create or approve a TCR for an employee with a target of 50M and sales of 20M ($40\%$).
2. Inspect the Commission Lines table in the Form View:
   - `Job Position`: Displays position name (e.g., "Property Consultant").
   - `Target Achievement`: Displays formatted `40%`.
   - `Current Commission`: Displays calculated commission (e.g., `60,000.0`).
3. Check manager cut lines:
   - Displays manager's supervisory job position.
   - Displays team's target achievement percentage.
   - Displays manager's cut amount under `Current Commission` (not 0.0).

---

## References

- Odoo Web Formatters: `addons/web/static/src/views/fields/formatters.js`
- Task reference: `DEV-031` in `brokerage-stage/Docs/LXET_DEVELOPER_TASKS.xlsx`
