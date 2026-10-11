# A Group Change in a noupdate="1" File Ships in Source but Never Reaches Existing Databases

| Field         | Value        |
|---------------|--------------|
| Category      | security     |
| Odoo Versions | All          |
| Severity      | 🔴 Critical  |
| Last Verified | 2026-08-14   |
| Author        | ENG/Gamal Mansour |

**Tags:** `res.groups`, `implied_ids`, `noupdate`, `migrations`, `access-rights`, `deployment`

---

## Problem

A UAT run surfaced an `AccessError`: Site Engineers could not issue material from store,
because issuing writes stock moves. The fix looked trivial — imply `stock.group_stock_user`
on the Site Engineer group:

```xml
<record id="group_site_engineer" model="res.groups">
    <field name="implied_ids" eval="[(4, ref('construction_contract.group_contract_user')),
                                     (4, ref('stock.group_stock_user'))]"/>
</record>
```

The module was upgraded, the suite stayed green, and the fix was considered shipped. It was
not. Querying the database afterwards:

```sql
SELECT g.name->>'en_US' AS grp, d.module || '.' || d.name AS implies
FROM res_groups_implied_rel r
JOIN res_groups g ON g.id = r.gid
JOIN ir_model_data d ON d.res_id = r.hid AND d.model = 'res.groups'
WHERE g.name->>'en_US' ILIKE '%Site Engineer%';

--      grp      |                  implies
-- ---------------+-------------------------------------------
--  Site Engineer | construction_contract.group_contract_user
-- (1 row)   <-- stock.group_stock_user is simply not there
```

The `AccessError` was still live — in every existing database — while the source read as fixed.

## Root Cause

The security file carried `noupdate="1"`:

```xml
<odoo>
    <data noupdate="1">
```

`noupdate="1"` tells Odoo: *load this record on first install, then never touch it again.*
It exists precisely so an administrator's own edits to the group hierarchy are not wiped by
every upgrade — legitimate and deliberate.

The consequence is that group edits split into two worlds:

| Path | Does the XML change apply? |
|------|---------------------------|
| Fresh install (`-i`) | ✅ yes |
| Upgrade of an existing DB (`-u`) | ❌ **no** |

This is the worst failure shape: it works on the developer's throwaway database, passes a
fresh-install smoke test, and silently does nothing on the customer's system. On odoo.sh it
bites hardest — test branches are restored from **production data**, so they are existing
databases, not fresh installs.

Tests do not catch it either: `TransactionCase` runs as SUPERUSER, which bypasses ACLs
entirely, so no test notices the missing right.

## Solution ✅

Do **not** remove `noupdate="1"` — that would trash administrator customisations on every
upgrade. Ship a migration script, which is ordinary module source and runs automatically:

```python
# construction_project/migrations/17.0.1.29.1/post-migration.py
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    site_engineer = env.ref('construction_project.group_site_engineer', raise_if_not_found=False)
    stock_user = env.ref('stock.group_stock_user', raise_if_not_found=False)
    if not site_engineer or not stock_user:
        return
    # Idempotent: re-running must not disturb a correct hierarchy, nor undo an
    # administrator who deliberately removed the right afterwards.
    if stock_user in site_engineer.implied_ids:
        return
    site_engineer.write({'implied_ids': [(4, stock_user.id)]})
```

Bump the manifest version to match the migration folder — **the folder name must equal the
new version or the script never runs**:

```python
'version': '17.0.1.29.1',   # migrations/17.0.1.29.1/post-migration.py
```

Writing `implied_ids` also grants the right to users who *already* hold the group:
`res.groups.write` cascades implied groups down to its members, so no separate user loop
is needed.

## ⚠️ Pitfalls

- The migration filename must start with `pre-`, `post-`, or `end-`. `migration.py` alone
  is ignored, silently.
- The folder name is the **new** version. Bumping the manifest without creating the folder
  (or vice versa) is a no-op with no warning.
- `-i` does **not** run migrations, only `-u` does — so you cannot verify this on a fresh
  database. Verify against a database that still holds the old state.
- Auditing which changes are affected: grep for group files carrying the flag, then check
  only those that define `implied_ids`.
  ```bash
  grep -rl 'noupdate="1"' --include="*.xml" */security/ | xargs grep -l implied_ids
  ```
- The same trap applies to any `noupdate="1"` data: `ir.rule` domains, sequences, mail
  templates, cron intervals. Changing them in XML never reaches an existing customer.
- Green tests prove nothing here — `TransactionCase` is SUPERUSER and never exercises ACLs.
- **Clearing `ir_model_data.noupdate` in SQL does not unlock the update.** The gate is the
  `<data noupdate="1">` attribute read from the FILE (`self.noupdate` in
  `odoo/tools/convert.py:_tag_record`); the database column is only a *second* check made
  later in `model._load_records()`. Flip the column, re-run `-u`, and the log still says
  `loading <module>/demo/foo.xml` while every existing record is skipped — the flag is not
  even re-stamped, which is the tell that nothing was processed.
- The same trap applies to **demo** files, which are almost always `noupdate="1"`. A
  migration script is the wrong tool there (you do not ship migrations to repair fixtures):
  fix the XML so every fresh install is correct, and bring existing databases in line with a
  one-off data script. Verify BOTH paths — the script proves the database, only a clean
  `-i` proves the XML.

## Verification

```bash
# Against a database that still has the OLD hierarchy:
./odoo-bin -d <db> -u construction_project --stop-after-init
# INFO ... odoo.modules.migration: module construction_project:
#          Running migration [17.0.1.29.1>] post-migration
```

Then confirm the right actually landed, and reached the group's members:

```sql
SELECT d.module || '.' || d.name
FROM res_groups_implied_rel r
JOIN ir_model_data d ON d.res_id = r.hid AND d.model = 'res.groups'
WHERE r.gid = (SELECT res_id FROM ir_model_data
               WHERE module='construction_project' AND name='group_site_engineer');
-- must now include stock.group_stock_user
```

## References

- Related file: `backend/env-su-guard-silently-passes-in-transactioncase.md`
- Related file: `backend/testing-access-error-base-group-user.md`
- Related file: `deployment/translate-true-change-crashes-until-module-upgrade.md`
- Related file: `security/consolidating-duplicate-groups-xmlid-rename-and-link-vs-replace.md`
- Related file: `views/demo-data-hardcoded-years-vs-date-range-constraints.md`
- Odoo source: `odoo/tools/convert.py` (`_tag_record`, the `self.noupdate` gate)
