# Odoo 19: `res.users.groups_id` Renamed to `group_ids` — Breaks Tests and Data Files

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `security`, `groups`, `res.users`, `group_ids`, `odoo19`, `testing`

---

## Problem

> Any code (tests, XML data, controllers) that creates or updates `res.users` with the
> classic `groups_id` field fails on Odoo 19 with an invalid-field error, because the
> field was renamed.

```
ValueError: Invalid field 'groups_id' on model 'res.users'
```

Typical broken code (worked on 15–18):

```python
self.env['res.users'].create({
    'name': 'Portal User',
    'login': 'portal_user',
    'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],  # ❌ Odoo 19
})
```

## Root Cause

In Odoo 19, `res.users` groups fields were reworked (`odoo/addons/base/models/res_users.py`):
- `groups_id` → **`group_ids`** (explicitly assigned groups)
- New computed field **`all_group_ids`** = groups + implied groups (use this for
  "does the user belong to X including implication" searches)

## Solution ✅

```python
self.env['res.users'].create({
    'name': 'Portal User',
    'login': 'portal_user',
    'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],  # ✅ Odoo 19
})
```

In XML data files use `<field name="group_ids" eval="..."/>` likewise.

## ⚠️ Pitfalls

- Modules copied forward from 17/18 carry `groups_id` silently in **tests** — they only
  explode when the test suite actually runs, not at install. Grep the whole module:
  `grep -rn "groups_id" custom_module/`
- Searching membership: `[('group_ids', 'in', ...)]` only matches *explicit* groups.
  For implied groups use `all_group_ids`.
- Related field on views/domains like `groups_id.name` in old server actions or
  automated rules will also break after migration — check `ir.actions.server` and
  `base.automation` records restored from a 17/18 backup.
- This is separate from the `res.groups.category_id` deprecation (see
  [odoo-19-res-groups-category-id-deprecation.md](odoo-19-res-groups-category-id-deprecation.md)).

## Versions

Verified on Odoo 19.0 source (`res_users.py` line ~257).
