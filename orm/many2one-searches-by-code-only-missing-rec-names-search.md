# Many2one autocomplete searches by CODE only — `_rec_name` is a code field and `_rec_names_search` is missing

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-09                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `many2one`, `name_search`, `_rec_names_search`, `_rec_name`, `name_get`, `autocomplete`

---

## Problem

A Many2one field (e.g. `boq_item_id` pointing at `project.boq.item`) autocompletes fine when the
user types the **code** (`1.3.2`), but typing part of the **description/name** ("concrete",
"بناء", "Excavation") returns **nothing**. Users conclude "the search only works by code".

```
# type "Excavation" in the BOQ Item dropdown -> 0 results
# type "1.3"        in the BOQ Item dropdown -> results appear
```

## Root Cause

The comodel sets `_rec_name` to a **code** field but never declares `_rec_names_search`.
Odoo's default `_name_search` (odoo/models.py) does:

```python
search_fnames = self._rec_names_search or ([self._rec_name] if self._rec_name else [])
```

With `_rec_names_search = None` it falls back to `[self._rec_name]` → only the code field is
searched. The `name` column is never part of the `ilike` OR-domain, so name typing matches nothing.

Two red herrings that do **NOT** fix search:
- A custom `_compute_display_name` (or legacy `name_get`) only changes how the record is **shown**
  in the widget — it has **zero** effect on which fields `name_search` queries.
- Adding a `domain` on the field (e.g. `execution_method='direct'`) filters candidates but does not
  change the searched fields.

## Solution ✅

Declare `_rec_names_search` on the comodel and list every field the user might type — **including
`name`** and any useful related field:

```python
class ProjectBoqItem(models.Model):
    _name = 'project.boq.item'
    _rec_name = 'full_code'
    # Without this, name_search falls back to _rec_name ('full_code') only,
    # so autocomplete matches by code and never by description/product name.
    _rec_names_search = ['full_code', 'name', 'product_id.name']
```

`_name_search` then builds an OR-domain across all listed fields
(`full_code ilike x OR name ilike x OR product_id.name ilike x`), so name typing works while the
display still shows `[full_code] name`.

**Deployment note (critical):** `_rec_names_search` is a plain Python class attribute baked into
the registry at **process import time**. Editing the file is not enough — the running Odoo worker
keeps the old registry in memory until it is **restarted** (or reloaded). Symptom of a stale
worker: the code on disk already lists `name` but the live dropdown still searches code-only.
Restart the server (a module `-u` is not required for a pure Python attribute).

## ⚠️ Pitfalls

- **`name_get` is deprecated in 17 and removed in 18.** If the model already overrides
  `_compute_display_name`, delete the duplicate `name_get` — it is dead code that only touches
  display, not search, and it breaks the Odoo 18 upgrade.
- Do NOT override `name_search` / `_name_search` to "add name" — `_rec_names_search` is the
  officially supported hook since Odoo 16. Overriding is harder to maintain and easy to get wrong.
- `full_code` via `ilike` already substring-matches leaf codes, so listing plain `code` too is
  usually redundant.
- Guard `_compute_display_name` against a falsy code:
  `f"[{rec.full_code}] {rec.name}" if rec.full_code else rec.name`.

## Verification

Test the exact form scenario (field domain included) in `odoo-bin shell` — no browser needed:

```python
M = env['project.boq.item']
print(M._rec_names_search)            # -> ['full_code', 'name', 'product_id.name']
res = M.name_search('Excavation', args=[('project_id','=',10),('execution_method','=','direct')])
print(len(res), res[:3])              # -> non-zero, matched by NAME
```

## References

- Core: `odoo/models.py` → `_name_search` (`search_fnames = self._rec_names_search or [self._rec_name]`)
- Related file: `orm/translated_many2one_search.md` (same hook, translated-field angle)
