# Construction Productivity Norms, Crew-Day Sizing & Site Factors Variance

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `productivity`, `norms`, `crew-sizing`, `site-factors`, `dpr`, `variance`, `zero-division`, `odoo18`

---

## Problem

Civil engineering and construction projects require monitoring field labor productivity against benchmark engineering norms (Egyptian Code, Saudi Aramco, SBC). In automated ERP implementations, tracking productivity directly against daily work orders presents two severe risks:

1. **Division-by-Zero and Astronomical Efficiency Spikes:**
   When combined site correction factors (such as deep ground water pumping -35%, scaffolding elevation > 3m -20%, summer heat -20%, and urban congestion -15%) are summed or compounded naively, expected productivity can drop to $\le 0$. If expected production is 0 or unpopulated, standard formulas $\text{Efficiency} = (\text{Executed} / \text{Expected}) \times 100$ crash with `ZeroDivisionError` or yield millions of percent.
2. **Inconsistent Crew Sizing Across Different Trades:**
   Comparing raw labor man-hours across dissimilar trades (e.g. 1 mason laying blocks vs a 10-man crew casting reinforced columns) creates false productivity alarms if unit conversions from man-hours to equivalent crew-days are omitted.

## Root Cause

1. Unbounded summation of environmental penalty coefficients without a mathematical lower clamp.
2. Failing to define standard crew compositions ($N_{\text{workers}} \times T_{\text{shift}}$) on the norm, preventing normalization of ad-hoc site labor into standardized crew-days.
3. Combining stored KPI scalars with non-stored HTML status banners inside the same `@api.depends` method, triggering Odoo 18 registry `UserWarning: inconsistent 'store' for computed fields`.

## Solution ✅

### 1. Model Standard Norms with Itemized Crew Lines

```python
class ConstructionProductivityNorm(models.Model):
    _name = 'construction.productivity.norm'
    _description = 'Construction Productivity Norm'

    name = fields.Char(string='Activity / Trade Name', required=True)
    code = fields.Char(string='Norm Code', required=True)
    standard_daily_output = fields.Float(string='Standard Daily Output / Crew', required=True, default=10.0)
    shift_hours = fields.Float(string='Standard Shift (Hours)', default=8.0)
    crew_line_ids = fields.One2many('construction.productivity.crew.line', 'norm_id', string='Standard Crew')
    total_crew_size = fields.Integer(compute='_compute_crew_metrics', store=True)
    man_hours_per_unit = fields.Float(compute='_compute_crew_metrics', store=True)

    @api.depends('crew_line_ids.worker_count', 'standard_daily_output', 'shift_hours')
    def _compute_crew_metrics(self) -> None:
        for rec in self:
            crew_size = sum(rec.crew_line_ids.mapped('worker_count'))
            rec.total_crew_size = crew_size
            daily_man_hours = crew_size * (rec.shift_hours or 8.0)
            rec.man_hours_per_unit = round(daily_man_hours / rec.standard_daily_output, 3) if rec.standard_daily_output > 0 else 0.0
```

### 2. Clamped Site Multiplier and Equivalent Crew-Day Derivation

```python
# Compute site adjustment with a safety floor of 10%
net_adj = sum(rec.site_factor_ids.mapped('adjustment_percentage'))
rec.combined_factor_percentage = net_adj
multiplier = max(0.10, 1.0 + (net_adj / 100.0))
rec.adjusted_daily_output = round(norm.standard_daily_output * multiplier, 2)

# Normalize deployed man-hours into standard crew-days
total_hours = sum((l.count or 1) * (l.hours or 8.0) for l in rec.labor_ids)
rec.actual_labor_man_hours = round(total_hours, 2)
crew_day_hours = (norm.total_crew_size or 1) * (norm.shift_hours or 8.0)
crew_days = (total_hours / crew_day_hours) if crew_day_hours > 0 else 0.0
rec.actual_crew_days_deployed = round(crew_days, 2)

# Compute expected vs executed output safely
expected_qty = round(crew_days * rec.adjusted_daily_output, 2)
rec.expected_output_for_crew = expected_qty

if expected_qty > 0 and rec.quantity_executed > 0:
    eff = round((rec.quantity_executed / expected_qty) * 100.0, 2)
    rec.productivity_efficiency = eff
    if eff >= 110.0:
        rec.productivity_status = 'exceptional'
    elif eff >= 90.0:
        rec.productivity_status = 'on_track'
    elif eff >= 75.0:
        rec.productivity_status = 'delayed'
    else:
        rec.productivity_status = 'critical'
```

### 3. Separate Stored Calculations from HTML Render Banners

To prevent Odoo 18 registry cache collisions and warnings, keep numeric metrics in a `store=True` compute method, and render the user alert banner in a separate `store=False` method.

---

## ⚠️ Pitfalls

- **Do not hardcode shift hours:** Use `norm.shift_hours` rather than assuming 8 hours. During Ramadan or extreme summer seasons, shifts are legally reduced to 6 hours in KSA and Egypt.
- **Always clamp the adjustment multiplier:** Multiple compounding negative site conditions must never reduce expected production to 0 or negative values (`max(0.10, factor)`).
- **Decouple DPR Hooks:** Fetch executed work orders via `_hook_fetch_daily_activities()` so daily site reports update automatically without tight model coupling.

---

## Verification

Run test suite:
```bash
./odoo-bin --test-enable --test-tags=construction_productivity -c odoo18_dev.conf -d odoo18_construction --stop-after-init
```
Expected output: `0 failed, 0 error(s) of 3 tests`.
