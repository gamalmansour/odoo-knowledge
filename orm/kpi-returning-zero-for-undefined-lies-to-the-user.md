# A KPI That Returns Zero for "Undefined" Lies to the User

| Field         | Value        |
|---------------|--------------|
| Category      | models       |
| Odoo Versions | All          |
| Severity      | 🟡 Medium    |
| Last Verified | 2026-08-05   |
| Author        | ENG/Gamal Mansour |

**Tags:** `kpi`, `evm`, `division-by-zero`, `ux`, `dashboard`, `computed-fields`

---

## Problem

An end-to-end pass on a clean database produced this on the project dashboard:

```
Project start 2026-09-01 · today 2026-08-05
EV = 300,000    PV = 0    SPI = 0.00
```

The Schedule Performance Index read **0.00** — which on any EVM dashboard means
*catastrophically behind schedule*. The truth was the exact opposite: work had been earned
**before the baseline even started**, so the project was ahead, not behind.

The number was not merely unhelpful. It was backwards, and a manager glancing at the KPI
would conclude either that the project had collapsed or that the software was broken.

## Root Cause

The classic guard against division by zero:

```python
spi = ev / pv if pv else 0.0
```

`0.0` is being used as "no answer", but for a ratio KPI zero is not a neutral placeholder —
it is the **worst possible value on the scale**. The guard silently converts *undefined*
into *terrible*.

SPI is genuinely undefined while PV is zero (nothing was planned to be done yet). Any single
number chosen to represent that is a lie: `0.0` says disaster, `1.0` says perfectly on plan.

## Solution ✅

Distinguish "no value" from "a bad value", and say **why** there is no value:

```python
spi = ev / pv if pv else 0.0
if pv:
    spi_note = False
elif not rec.date_start:
    spi_note = _('No baseline start date')
elif today < rec.date_start:
    spi_note = _('Baseline starts %s') % rec.date_start
else:
    spi_note = _('No planned value yet')

rec.spi            = spi
rec.spi_measurable = bool(pv)
rec.spi_note       = spi_note
```

Swap the field in the view rather than dressing up the number — a Float always renders as a
number, so the only way to show "not applicable" is to show a different field:

```xml
<field name="spi_measurable" invisible="1"/>
<field name="spi" readonly="1" invisible="not spi_measurable"
       decoration-danger="spi &lt; 1" decoration-success="spi &gt;= 1"/>
<field name="spi_note" string="SPI (Schedule Performance)"
       readonly="1" invisible="spi_measurable"/>
```

Any programmatic consumer (dashboards, reports, APIs) must be updated in the same pass, or it
keeps publishing the misleading zero:

```python
'spi': Project.spi if Project.spi_measurable else None,
'spi_measurable': Project.spi_measurable,
'spi_note': Project.spi_note,
```

Result — the honest reading, side by side with genuinely bad projects:

```
PRJ/0006 · EV 300,000   · PV 0          · SPI — (Baseline starts 2026-09-01)
PRJ/0005 · EV 0         · PV 92,000,000 · SPI 0.00     <-- really is stalled
PRJ/0004 · EV 2,700,260 · PV 8,200,000  · SPI 0.33     <-- really is behind
```

Zero now means zero.

## ⚠️ Pitfalls

- Audit every consumer, not just the form: `grep -rn "'spi'\|\.spi\b" --include="*.py"`.
  A dashboard left untouched keeps shipping the lie to the very audience the KPI is for.
- The same trap covers every ratio KPI: CPI (`ev/ac`), SPI, DSO, utilisation %, win rate,
  margin %. Ask what a caller would conclude from the fallback, not just whether it crashes.
- Do not "fix" it with `1.0` either — that claims the project is exactly on plan, which is a
  different lie.
- A non-stored compute cannot be searched or grouped; if the KPI must be filterable, the
  measurability flag has to be stored, not the ratio.

## Verification

Build a project whose baseline has not started, one mid-flight, and one genuinely behind, and
assert the first is flagged unmeasurable while the others still report real numbers:

```python
def test_spi_is_unmeasurable_before_the_baseline_starts(self):
    project = self._project(start_offset_months=1, end_offset_months=13)
    self.assertEqual(project.planned_value, 0.0)
    self.assertFalse(project.spi_measurable)
    self.assertTrue(project.spi_note, "the user must be told why SPI is missing")
```

## References

- Related file: `backend/int-cast-on-config-parameter-crashes-on-human-input.md`
- Related file: `setup/module-needs-a-setting-odoo-ships-disabled.md`
