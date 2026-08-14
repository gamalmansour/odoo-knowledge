# Demo Data With Hard-Coded Years Silently Rots Once the Calendar Passes It

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `demo`, `constraints`, `date-range`, `time-bomb`, `xmlid`, `install`, `qa-checklist`

---

## Problem

Demo XML pins period records to fixed years while the transactional demo records that
point at them are written relative to `now`:

```xml
<!-- the cycle: hard-coded 2026 -->
<field name="start_date" eval="(datetime.now().replace(day=1, month=1, year=2026)).strftime('%Y-%m-%d')"/>
<field name="end_date"   eval="(datetime.now().replace(day=31, month=3, year=2026)).strftime('%Y-%m-%d')"/>

<!-- the visit: relative to today -->
<field name="date_planned" eval="(DateTime.now() + timedelta(days=2)).strftime('%Y-%m-%d 10:00:00')"/>
```

A model constraint ties the two together:

```python
@api.constrains('date_planned', 'cycle_id')
def _check_cycle_dates(self):
    if not (record.cycle_id.start_date <= planned_date <= record.cycle_id.end_date):
        raise ValidationError(_("Planned visit date must fall within the cycle period."))
```

The demo installs fine for a few months, then — with **no code change at all** — every
install past the last hard-coded end date raises `ValidationError` inside `load_demo`,
which swallows it:

```
WARNING ... Module medical_call_visit demo data failed to install, installed without demo data
```

Install still exits 0. Screens are empty. Nothing in the diff explains it, because
nothing changed except the date.

## Root Cause

`load_demo` wraps each module's demo in a savepoint and catches **every** exception,
so a `ValidationError` from a date-range `@api.constrains` is indistinguishable from a
missing xmlid — both just set `ir_module_module.demo = false` and continue. Hard-coded
years turn the demo into a dated artifact whose expiry is invisible until it passes.

## Solution ✅

Anchor **every** period record to the install date, and size the window so it always
contains the relative offsets used by dependent demo records:

```xml
<!-- current cycle: [start of last month .. end of next month] always contains now +/- 15d -->
<record id="cycle_current" model="medical.territory.cycle">
    <field name="name" eval="'Planning Cycle ' + (datetime.now() - relativedelta(months=1)).strftime('%b') + '-' + (datetime.now() + relativedelta(months=1)).strftime('%b %Y')"/>
    <field name="start_date" eval="(datetime.now() - relativedelta(months=1)).replace(day=1).strftime('%Y-%m-%d')"/>
    <field name="end_date" eval="((datetime.now() + relativedelta(months=2)).replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')"/>
    <field name="status">active</field>
</record>
```

Name the xmlids by **role** (`cycle_previous` / `cycle_current` / `cycle_next`), not by
period (`cycle_q1_2026`) — an id that says 2026 while holding rolling dates is a lie the
next reader will act on. `relativedelta`, `datetime`, `timedelta`, `DateTime` and
`time` are all available in the demo eval context (`odoo/tools/convert.py:_get_idref`).

Assert the window really brackets the offsets after install:

```sql
SELECT v.name, v.date_planned::date, c.name,
       (v.date_planned::date BETWEEN c.start_date AND c.end_date) AS inside
FROM medical_call_visit v JOIN medical_territory_cycle c ON c.id = v.cycle_id;
-- every row must be inside = t
```

## ⚠️ Pitfalls

- Windows sized exactly to the offsets (`now-5d .. now+7d`) break when the demo is
  installed near a month boundary — leave a month of slack on each side.
- Only ONE period record should be `active` if the model has an overlap constraint
  (`_check_overlapping_cycles`); make previous `closed` and next `draft`.
- `datetime.now().replace(month=..., year=...)` also raises `ValueError` on Feb 29 /
  day-31 months — another reason to build dates with `relativedelta`, not `replace`.
- A visit constraint like `_check_hcp_territory` guarded by
  `hasattr(record.hcp_id, 'territory_id')` is **dead code** — Odoo recordsets raise
  `AttributeError` for undeclared fields, so `hasattr` is always `False`. It will not
  save you, and it hides the fact that the field was never added.

## Verification

```bash
dropdb --if-exists verify_db && createdb verify_db
python3 odoo-bin -c conf -d verify_db -i <top_module> --stop-after-init --log-level=info > install.log 2>&1
grep -c "demo data failed" install.log     # must be 0
psql -d verify_db -tAc "SELECT name FROM ir_module_module WHERE name LIKE 'my_prefix_%' AND state='installed' AND NOT demo;"   # must be empty
```

To load demo into a database that was created `--without-demo`, there is no per-module
switch — `should_have_demo()` requires every parent module to carry the demo flag too.
Use the supported all-modules path (same code as the Settings "Load demo data" button):

```python
from odoo.modules.loading import force_demo
force_demo(env)   # via: odoo-bin shell -d <db>
```

## References

- Related file: `views/demo-data-cross-module-refs-load-order.md`
- Related file: `setup/clean-db-install-verification-demo-as-data-and-missing-rule-fields.md`
- Odoo source: `odoo/modules/loading.py` (`load_demo`, `force_demo`), `odoo/modules/graph.py` (`should_have_demo`)
