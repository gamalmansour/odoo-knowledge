# Consolidating Duplicate Security Groups: Rename the XMLID, and Fix (4,…) vs (6,0,…) First

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `res.groups`, `ir.rule`, `migration`, `xmlid-rename`, `implied_ids`, `upgrade`, `foreign-key`

---

## Problem

A multi-module suite where each module declared its own copy of the same roles
(MR / DM / SM / Admin) — 14 groups where 4 were meant, three of them sharing the
literal label "Medical Representative", none linked across modules by
`implied_ids`. One rep needed four separate group assignments and any missed one
produced an empty screen or an AccessError.

Consolidating them into one canonical set fails twice before it works:

```
ERROR odoo.sql_db: bad query: INSERT INTO "res_groups" (...) VALUES (...)
ERROR: duplicate key value violates unique constraint "res_groups_name_uniq"
CRITICAL odoo.service.server: Failed to initialize database
```

then, after fixing that:

```
ERROR odoo.sql_db: bad query: DELETE FROM "res_groups" WHERE id IN (38)
ERROR: update or delete on table "res_groups" violates foreign key constraint
       "rule_group_rel_group_id_fkey" on table "rule_group_rel"
```

Both abort the whole registry load — the database is left un-upgradable, not
partially upgraded.

## Root Cause

**Failure 1 — the retired groups are still there.** Records dropped from a data
file are removed by `ir.model.data._process_end`, which runs *after the entire
module graph is loaded*. So while the new canonical group is being INSERTed, the
old group with the same `(category_id, name)` still exists, and `res_groups`
carries `UNIQUE(category_id, name)`.

**Failure 2 — `(4, …)` is LINK, not REPLACE.** Record rules are conventionally
written as:

```xml
<field name="groups" eval="[(4, ref('group_x'))]"/>
```

Repointing a rule at a new group therefore *adds* it and keeps the old link in
`rule_group_rel`. When cleanup then tries to delete the retired group, the
surviving link trips the foreign key.

## Solution ✅

**1. Make `ir.rule.groups` authoritative — `(6, 0, [...])`, not `(4, …)`:**

```xml
<!-- WRONG: link-only, stale group links survive every upgrade -->
<field name="groups" eval="[(4, ref('medical_hcp.group_medical_crm_sm')), (4, ref('medical_hcp.group_medical_crm_admin'))]"/>

<!-- RIGHT: the declared list IS the list -->
<field name="groups" eval="[(6, 0, [ref('medical_hcp.group_medical_crm_sm'), ref('medical_hcp.group_medical_crm_admin')])]"/>
```

Keep `(4, …)` for **`implied_ids`** — that one is meant to be additive so other
modules can extend a group. The price is that a stale implication edge from a
previous file version is never removed; prune it explicitly in post-migrate.

**2. Rename the xmlid instead of creating a new record.** For groups the base
module already owns, a `pre-migrate.py` rename means the loader updates the
existing row: no INSERT, no unique-constraint collision, same `res.groups.id`,
and `res_groups_users_rel` is never touched so nobody loses access.

```python
def migrate(cr, version):
    if not version:
        return
    for old_name, new_name in XMLID_RENAMES.items():
        cr.execute("SELECT 1 FROM ir_model_data WHERE module=%s AND model='res.groups' AND name=%s",
                   ('medical_hcp', new_name))
        if cr.fetchone():          # already renamed — UNIQUE(module,name) would blow up
            continue
        cr.execute("UPDATE ir_model_data SET name=%s WHERE module=%s AND model='res.groups' AND name=%s",
                   (new_name, 'medical_hcp', old_name))
```

**3. Move memberships of the *other* modules' duplicates in `post-migrate.py`.**
Post is the only correct hook: the canonical groups exist by then (a module's
data loads before its post scripts) while the retired ones are still alive
(cleanup runs at the very end). Write on the **user** side so `implied_ids`
expands:

```python
users = old_group.users - new_group.users
users.write({'groups_id': [(4, new_group.id)]})   # NOT old_group.users / new_group.users
```

**4. Put the canonical groups in the module every other module depends on.**
Anything lower in the graph cannot be referenced by its dependencies.

## ⚠️ Pitfalls

- `res_groups` UNIQUE is on `(category_id, name)`, not name alone — two groups
  called "District Manager" coexist happily in *different* categories, which is
  exactly how duplicate hierarchies hide in the Users form.
- Deleting the duplicate `ir.module.category` records too, or the retired groups
  keep a category alive with nothing in it.
- Unprefixed `group_x` in `ir.model.access.csv` resolves to the **local** module.
  After moving a group, every CSV outside the owning module needs the
  `owning_module.` prefix or the ACL silently points at a non-existent xmlid.
- The migration only runs when the manifest version is **higher** than
  `ir_module_module.latest_version`. To replay it while testing:
  `UPDATE ir_module_module SET latest_version='<old>' WHERE name='<module>';`

## Verification

```bash
# 1. upgrade path
python3 odoo-bin -c conf -d existing_db -u <all modules> --stop-after-init
psql -d existing_db -tAc "SELECT count(*) FROM ir_model_data WHERE model='res.groups' AND module LIKE 'my_prefix%';"   # == canonical count

# 2. fresh install path (the migration does NOT cover this)
dropdb --if-exists fresh && createdb fresh
python3 odoo-bin -c conf -d fresh -i <top module> --stop-after-init
```

Then assert the real behaviour — one group assignment must unlock every module:

```python
user = env['res.users'].create({'name': 'T', 'login': 't', 'groups_id': [(6, 0, [mr_group.id])]})
for model in ('medical.territory.territory', 'medical.call.visit', 'medical.coaching.session', ...):
    env[model].with_user(user).search_count([])   # must not raise AccessError
```

## References

- Related file: `security/extending-portal-groups-to-internal-users-implied-unlink.md`
  — same class of bug from the other direction: deleting an `implied_ids` line
  from the XML does NOT remove the link already stored in the database.
- Related file: `security/noupdate-group-change-never-reaches-existing-databases.md`
- Odoo source: `odoo/addons/base/models/ir_model.py` (`ir.model.data._process_end`),
  `odoo/modules/migration.py`
