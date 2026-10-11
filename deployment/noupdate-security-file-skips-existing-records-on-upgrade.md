# A noupdate security file silently skips EXISTING records on upgrade

**Category:** Deployment / Security
**Date:** 2026-08-10
**Project:** activity (five per-app groups, night before go-live)

## Symptom
New `implied_ids` were added to an existing group (`group_activity_admin` should imply five new app groups). Fresh install: correct. Upgrade of a real deployed database: the implications simply **were not there** — no error, no warning. The back office behaved differently depending on how the database was born.

## Root cause
`security/*.xml` is conventionally `<odoo noupdate="1">`. Odoo stamps that flag onto each record's **`ir.model.data.noupdate`** row at first install. On every later upgrade the loader skips those records — *regardless of which file re-declares them*. Moving the declaration into a second, updatable file does NOT help: the flag lives on the DATA ROW, not the file.

New records ARE created (noupdate only blocks updates), which is why the five new groups appeared while the change to the existing group did not — the most confusing possible half-state.

## Fix (both halves are needed)
1. **For fresh installs:** declare the new groups + the implication in a separate file WITHOUT `noupdate`, loaded after the noupdate one.
2. **For deployed databases:** a migration script — the only thing that can touch an already-stamped record:
```python
# <module>/migrations/<new-version>/post-app_group_implications.py
def migrate(cr, version):
    if not version:
        return                      # fresh install: XML already did it
    env = api.Environment(cr, SUPERUSER_ID, {})
    admin = env.ref('...group_activity_admin', raise_if_not_found=False)
    to_link = [g for x in APP_GROUPS if (g := env.ref(x, raise_if_not_found=False))
               and g not in admin.implied_ids]
    if to_link:
        admin.write({'implied_ids': [(4, g.id) for g in to_link]})
    # let the updatable XML own it from now on — no migration needed next time
    env['ir.model.data'].search([...('name','=','group_activity_admin')]).write({'noupdate': False})
```
Bump the manifest `version` or the migration never runs.

## Sibling trap in the same change: menuitem `groups` only ADDS
`tools/convert.py::_tag_menuitem` builds `Command.link` for each group and `Command.unlink` only for a `-`-prefixed one. Changing `groups="A"` to `groups="B"` leaves an upgraded database with **both** A and B while a fresh install has only B. Write `groups="B,-A"` — the unlink is a harmless no-op on a fresh install.

## Rule of thumb
Any security/data change that edits an EXISTING record needs an upgrade rehearsal on a restored production backup, not just a fresh install. "Works on a clean DB" proves nothing about the customer's DB.
