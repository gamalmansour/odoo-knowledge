# An `ir.cron` Without `numbercall` Runs ONCE and Then Stops — Silently, Forever

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                         |
| Odoo Versions | All                                         |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-08-19                                  |
| Author        | ENG/Gamal Mansour                           |

**Tags:** `orm`, `ir.cron`, `numbercall`, `scheduled-action`, `data-file`, `silent-failure`, `gc`, `reconciliation`

---

## Problem

A cron declared in a data file looks completely normal and works the first time:

```xml
<record id="cron_reconcile_payments" model="ir.cron">
    <field name="name">Gateway: reconcile pending payments</field>
    <field name="model_id" ref="model_payment_transaction"/>
    <field name="state">code</field>
    <field name="code">model._cron_reconcile()</field>
    <field name="interval_number">3</field>
    <field name="interval_type">minutes</field>
    <field name="active" eval="True"/>
</record>
```

It runs once. Then it never runs again — for the life of the database.

There is **no error, no traceback, no log line, and no warning**. In Settings ▸
Technical ▸ Scheduled Actions the record is still there and still shows
**Active = ✓**, with a `nextcall` in the past that simply never advances.

Whatever the cron was responsible for silently stops: garbage collection stops
(tables grow forever), generated records stop being generated, and — the case
that produced this entry — a *payment reconciliation* cron stopped, so every
customer whose gateway webhook was lost sat unpaid indefinitely.

## Root Cause

`ir.cron.numbercall` defaults to **1**:

```python
# odoo/addons/base/models/ir_cron.py
numbercall = fields.Integer(string='Number of Calls', default=1,
    help='How many times the method is called,\na negative number indicates no limit.')
```

After each run the remaining count is decremented and written back:

```python
call_count_left = max(job['numbercall'] - effective_call_count, -1)
...
UPDATE ir_cron SET nextcall=%s, numbercall=%s, lastcall=%s, active=%s WHERE id=%s
```

`1 - 1 = 0`. And the scheduler's own selection query excludes zero:

```sql
SELECT * FROM ir_cron
 WHERE active = true
   AND numbercall != 0          -- <-- the cron disappears here
   AND (nextcall <= (now() at time zone 'UTC') OR ...)
```

So `active` stays `True` — which is exactly why nobody notices — while the job
is permanently invisible to `_get_all_ready_jobs`.

Odoo core never hits this because essentially every core cron declares it. In
Odoo 17 there are ~66 `<field name="numbercall">-1</field>` lines across the
standard addons; a recurring core cron *without* it does not exist.

## Solution ✅

Declare `-1` (= no limit) on every recurring cron:

```xml
<record id="cron_reconcile_payments" model="ir.cron">
    ...
    <field name="numbercall">-1</field>
    <field name="interval_number">3</field>
    <field name="interval_type">minutes</field>
    <field name="active" eval="True"/>
</record>
```

**Existing databases need a repair.** Cron data files normally carry
`noupdate="1"` (correctly — an upgrade must not stamp over an operator's
schedule), so fixing the XML does nothing for databases already installed. Add a
migration:

```python
def migrate(cr, version):
    cr.execute("""
        UPDATE ir_cron c
           SET numbercall = -1
          FROM ir_model_data d
         WHERE d.model = 'ir.cron'
           AND d.res_id = c.id
           AND d.module LIKE 'mymodule\\_%'
           AND c.numbercall = 0
    """)
```

Keep it narrow — only *your* modules, and only crons already exhausted
(`numbercall = 0`), so an operator who deliberately set a finite count on a job
that still has calls left is not overridden.

**Guard it with a structural test.** The failure is invisible at runtime, so the
check belongs at the definition:

```python
def test_no_cron_can_exhaust_itself(self):
    data = self.env['ir.model.data'].sudo().search([('model', '=', 'ir.cron')])
    ids = data.filtered(lambda d: d.module.startswith('mymodule')).mapped('res_id')
    offenders = [c.name for c in self.env['ir.cron'].browse(ids).exists()
                 if c.numbercall != -1]
    self.assertFalse(offenders, 'These crons will stop running: %s' % offenders)
```

## ⚠️ Pitfalls

- **`active` stays `True`.** Every "is my cron enabled?" check — the UI, a
  support script, a monitoring query — says yes. Assert on `numbercall`, not on
  `active`.
- **It passes every test and every demo.** A single run is exactly what a test
  DB, a demo, and a manual "Run Manually" click all exercise. The bug only
  appears on the *second* scheduled tick, i.e. never before production.
- **It masks other bugs.** An unbatched `search([...]).unlink()` in a GC cron
  looks harmless in review because the table never grows — the cron that would
  have grown it stopped on day one. Fixing `numbercall` can therefore *surface*
  a second latent bug the same day; batch the GC in the same change.
- **`noupdate="1"` means the XML fix reaches new installs only.** Without the
  migration you will "fix" this and every existing customer stays broken.
- **`doall` interacts with it.** With `doall=True` and a finite `numbercall`,
  missed occurrences are replayed up to `min(missed, numbercall)` — another way
  to burn the budget faster than expected. `-1` sidesteps it.
- Don't "fix" it by ticking `active` in the UI: `active` was never the problem,
  and re-ticking it does not reset `numbercall`.

## Verification

```sql
-- Any of your crons already dead?
SELECT c.id, c.name, c.active, c.numbercall, c.nextcall, c.lastcall
FROM   ir_cron c
JOIN   ir_model_data d ON d.model = 'ir.cron' AND d.res_id = c.id
WHERE  d.module LIKE 'mymodule\_%'
ORDER  BY c.numbercall;
-- numbercall = 0  -> dead (note active is still true)
-- numbercall = 1  -> will die after its next run
-- numbercall = -1 -> healthy
```

A live symptom worth checking too: `lastcall` far in the past while `nextcall`
is also in the past and never moves.

## References

- `odoo/addons/base/models/ir_cron.py` — `numbercall` default, `_get_all_ready_jobs`
- Related file: `setup/neutralized-test-backup-in-production-reactivate-crons-from-source-defaults.md`
