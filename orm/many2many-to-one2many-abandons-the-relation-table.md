# Converting Many2many to One2many Abandons the Relation Table (and Revives Dead Guards)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `many2many`, `one2many`, `migration`, `hasattr`, `constraints`, `data-loss`, `parent_path`

---

## Problem

A model owned one half of a relation as a Many2many while the *other* side was
never declared — a classic "the other module will add it" TODO that nobody came
back to:

```python
# medical_hcp/models/res_partner.py
# Note: territory_id will be added by medical_territory module     <-- never happened
```

Two things go wrong when you finally close it.

**A. Changing the field type silently drops the data.** Turning
`hcp_ids = fields.Many2many('res.partner', 'territory_hcp_rel', ...)` into
`fields.One2many('res.partner', 'territory_id')` makes Odoo stop reading
`territory_hcp_rel` entirely. It neither migrates nor drops the table: the
upgrade succeeds, exit code 0, and every existing assignment is gone from the UI.

**B. A guard written against the missing field was never running.** The
constraint that depended on it read:

```python
if hasattr(record.hcp_id, 'territory_id') and record.hcp_id.territory_id:
    ...raise ValidationError(...)
```

An Odoo recordset raises `AttributeError` for an undeclared field, so `hasattr`
is **always False** — the constraint had been inert since the day it was
written, and it looks defensive in review. Declaring the field flips it live
retroactively, and every record that was inconsistent while nobody was checking
now raises on its next write.

## Root Cause

Odoo's schema update only ever adds columns and tables; it never rewrites a
relation whose *storage shape* changed. `Many2many` lives in its own rel table,
`One2many` is just a reverse index over the comany2one column — there is no
common ground for the ORM to migrate automatically.

`hasattr` on a recordset routes through `__getattr__`, which raises for unknown
fields; `hasattr` swallows that into `False`. It is never a valid way to
feature-detect an Odoo field.

## Solution ✅

**1. Carry the rows over in a post-migrate** (post, not pre: the new column is
created during the schema update):

```python
def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('public.territory_hcp_rel')")
    if not cr.fetchone()[0]:
        return
    # A Many2many could hold what a One2many cannot — report before collapsing.
    cr.execute("""SELECT partner_id, count(*) FROM territory_hcp_rel
                   GROUP BY partner_id HAVING count(*) > 1""")
    for partner_id, n in cr.fetchall():
        _logger.warning("partner %s was in %s territories; keeping the lowest id", partner_id, n)
    cr.execute("""
        UPDATE res_partner p SET territory_id = sub.territory_id
          FROM (SELECT DISTINCT ON (partner_id) partner_id, territory_id
                  FROM territory_hcp_rel ORDER BY partner_id, territory_id) sub
         WHERE p.id = sub.partner_id AND p.territory_id IS NULL
    """)
```

Do **not** drop the old table in the same script — leave it until the result has
been reviewed.

**2. Delete the `hasattr` guard** and make the check real. For a
`_parent_store` hierarchy, compare branches rather than identity, or you will
reject legitimate parent/child cases:

```python
hcp_path = hcp_territory.parent_path or ''       # "1/5/12/"
visit_path = record.territory_id.parent_path or ''
if hcp_path.startswith(visit_path) or visit_path.startswith(hcp_path):
    continue                                      # same branch: ancestor, self or descendant
raise ValidationError(...)
```

**3. Make the demo/seed data consistent BEFORE the constraint goes live**, and
put the cross-module assignment in the module that owns the new field — the
module declaring it loads after the one holding the records.

**4. Check the call sites survive the type change.** `len(x.field_ids)` and
`x.field_ids.ids` behave identically on M2M and O2M, so most code is untouched;
what breaks is views — `<field name="x_ids" widget="many2many">` must lose the
widget on a One2many.

## ⚠️ Pitfalls

- `hasattr(recordset, 'field')` is always False for an undeclared field and
  always True once declared — never feature-detect a field that way. Use
  `'field' in record._fields`.
- Reviving a dormant constraint is a behaviour change on **existing** data, not
  just new records. Constraints fire on write, so old rows stay silently
  inconsistent until someone edits them — audit them explicitly.
- The demo file is `noupdate="1"`: fixing the XML does not touch databases where
  the demo is already loaded. See
  `security/noupdate-group-change-never-reaches-existing-databases.md`.
- `_order = 'parent_left'` on a `_parent_store` model is Odoo ≤11 legacy —
  `parent_left`/`parent_right` were replaced by `parent_path` in 12.0. If the
  column is still declared but never computed, the model is ordering by an
  all-NULL column and the tree order is effectively arbitrary.

## Verification

```bash
# fresh install proves the XML; the migration is only exercised by -u
dropdb --if-exists fresh && createdb fresh
python3 odoo-bin -c conf -d fresh -i <top module> --stop-after-init
grep -c "demo data failed" install.log     # must be 0 — a revived constraint shows up here
```

Then assert the constraint discriminates instead of just passing:

```python
# HCP is in "Riyadh North Area"
create(territory=riyadh_north)    # same        -> accepted
create(territory=riyadh_zone)     # ancestor    -> accepted
create(territory=jeddah_central)  # other branch-> ValidationError
```

## References

- Related file: `security/noupdate-group-change-never-reaches-existing-databases.md`
- Related file: `views/demo-data-cross-module-refs-load-order.md`
- Related file: `views/demo-data-hardcoded-years-vs-date-range-constraints.md`
