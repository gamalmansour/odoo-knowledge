# Falsy field interpolated into an f-string bakes the literal `"False"` into a stored computed field

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-09                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `store`, `f-string`, `false`, `display_name`, `full_code`, `recursive`

---

## Problem

A stored computed `Char` builds a composite code by joining a parent value with an
own value via an f-string. When the own value is **falsy** (`False` / empty), Python
renders it as the literal string `"False"`, which gets **stored** in the DB and shown
to users:

```
# project.boq.item.full_code seen in a Many2one dropdown:
[1.1.False] Excavation & backfilling crew
[8.4.False] Concrete pouring crew
```

Live example: on a real DB, **116 of 218** `project.boq.item` rows had `full_code`
containing `False` — every level-3 breakdown line (material/labor/equipment) and
section header, because those rows are not required to carry their own `code`.

```python
# BUGGY
@api.depends('code', 'parent_id.full_code')
def _compute_full_code(self):
    for rec in self:
        if rec.parent_id:
            rec.full_code = f"{rec.parent_id.full_code}.{rec.code}"  # rec.code is False -> ".False"
        else:
            rec.full_code = rec.code
```

## Root Cause

`f"{x}"` calls `str(x)`. For an Odoo `Char`/`Selection`/`Many2one` that is empty, the
ORM value is the Python bool `False`, and `str(False) == "False"`. The `if rec.parent_id`
guard only checks the *parent*, never whether the *own* field is empty — so the falsy
own value is interpolated verbatim.

Two compounding traps:
- **The field is `store=True`.** The bad string is written to the column, so it survives
  in every existing DB even after the code is fixed — a pure code fix does **not**
  rewrite historic rows.
- **A `display_name` falsy-guard does not save you.** `f"[{full_code}] {name}" if full_code else name`
  never triggers, because `full_code` is now the **truthy** string `"1.1.False"` — the
  guard only catches an empty `full_code`, not a poisoned one. (See
  `orm/many2one-searches-by-code-only-missing-rec-names-search.md`, which guards
  `display_name` but not the upstream compute.)

## Solution ✅

Never interpolate a value you have not proven truthy. Coerce empties to `''` and only
add the dotted separator when **both** sides are present, so a codeless node inherits
its parent path (and a codeless root becomes `''`):

```python
@api.depends('code', 'parent_id.full_code')
def _compute_full_code(self):
    for rec in self:
        parent_code = rec.parent_id.full_code if rec.parent_id else ''
        own_code = rec.code or ''
        if parent_code and own_code:
            rec.full_code = f"{parent_code}.{own_code}"
        else:
            rec.full_code = parent_code or own_code or ''
```

This never emits `False`, and never a leading/trailing/double dot.

**Recompute the stored data (mandatory).** Because the field is stored, add a migration
that forces a recompute so existing DBs self-heal on `-u`. Bump the manifest version
(e.g. `…0.12` → `…0.13`) so the migration folder is picked up:

```python
# migrations/17.0.1.0.13/post-migration.py
from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    records = env['project.boq.item'].with_context(active_test=False).search([])
    if not records:
        return
    records.invalidate_recordset(['full_code'])
    records.modified(['code'])   # mark dependents dirty via the trigger graph
    env.flush_all()              # recompute (respects recursive parent->child ordering)
```

`modified()` + `flush_all()` routes through the ORM trigger graph, so a `recursive=True`
compute is recomputed parents-before-children automatically — safer than calling
`_compute_full_code()` directly in arbitrary record order.

## ⚠️ Pitfalls

- **Don't rely on `if rec.parent_id` alone.** It says nothing about whether `rec.code`
  (the value you interpolate) is empty. Guard the interpolated operand, not a sibling.
- **A code-only fix leaves poisoned rows.** Always pair the compute fix with a recompute
  (migration for shipped DBs; a one-off `records.modified([...]); env.flush_all()` in
  `odoo-bin shell` for a live DB).
- **The same trap hides in `name_get`/`_compute_display_name`, mail templates and QWeb**
  — anywhere `f"{a}.{b}"`, `"%s" % x`, or `str.format` touches a possibly-empty ORM
  field. Grep for `f"{...{self.<field>}...}"` on non-required fields.
- **Uniqueness:** falling back to the parent path means codeless siblings collapse to the
  same `full_code` (e.g. three breakdown lines all show `1.1`). That is fine when
  `full_code` is only a display/`_rec_name`/`_rec_names_search` helper with no `unique`
  SQL constraint — the description disambiguates. If it were a real key, append the
  `sequence`/`id` instead.

## Verification

In `odoo-bin shell` (no browser needed) — prove zero poisoned rows and clean display:

```python
Boq = env['project.boq.item']
recs = Boq.search([])
recs.invalidate_recordset(['full_code']); recs.modified(['code']); env.flush_all()
bad = recs.filtered(lambda r: r.full_code and 'False' in r.full_code)
print(len(bad))                                  # -> 0
print(recs[:3].mapped('display_name'))           # -> ['[1.1] Excavation & backfilling crew', ...]
```

Or straight SQL after `-u`:

```sql
SELECT count(*) FROM project_boq_item WHERE full_code LIKE '%False%';  -- 0
```

## References

- Related: `orm/many2one-searches-by-code-only-missing-rec-names-search.md` (same model;
  guards `display_name` but not the upstream `_compute_full_code`)
- Related: `orm/stored-compute-parent-stale-sequential-child-create.md` (stored recursive
  compute + migration recompute mechanics)
