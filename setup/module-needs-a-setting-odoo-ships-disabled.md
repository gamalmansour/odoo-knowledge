# A Module That Needs a Setting Odoo Ships Disabled Crashes on First Use

| Field         | Value        |
|---------------|--------------|
| Category      | setup        |
| Odoo Versions | 17, 18, 19   |
| Severity      | 🔴 Critical  |
| Last Verified | 2026-08-05   |
| Author        | ENG/Gamal Mansour |

**Tags:** `post_init_hook`, `stock`, `picking-type`, `fresh-install`, `active-test`, `demo-readiness`

---

## Problem

Issuing material from store to site — a core act of any construction ERP — failed on a
freshly installed database the very first time it was used:

```
odoo.exceptions.UserError: No internal transfer operation type found for company My Company.
```

Nothing was misconfigured by the user. The module had just been installed and the first
real operation crashed. The developer database never showed it, because months earlier
someone had enabled Storage Locations there by hand.

## Root Cause

The code looks correct:

```python
picking_type = self.env['stock.picking.type'].search([
    ('code', '=', 'internal'), ('company_id', '=', rec.work_order_id.company_id.id)
], limit=1)
```

But on a fresh database the internal picking types **exist and are archived**:

```sql
SELECT code, active, count(*) FROM stock_picking_type GROUP BY 1,2;
--   code   | active | count
-- ---------+--------+-------
--  incoming| t      |     2
--  internal| f      |     6     <-- all six archived
--  outgoing| t      |     2
```

Odoo ships internal transfers switched off until **Storage Locations**
(`stock.group_stock_multi_locations`) is enabled in Inventory settings. A plain `search()`
applies `active_test=True` and silently skips archived records, so the lookup returns empty
and the feature dies with a message that sounds like corrupt data rather than a missing
setting.

A module whose core workflow depends on a setting Odoo disables by default must turn that
setting on itself. Leaving it to the user means the first demo, the first evaluation, and
the first day of real use all begin with a crash.

## Solution ✅

Declare a `post_init_hook` that enables the required setting.

**Enabling the group is not sufficient.** `stock` activates the picking types as a separate,
explicit step inside its own settings wizard (`stock/models/res_config_settings.py`), so the
hook has to mirror both halves:

```python
# construction_project/__init__.py
def post_init_hook(env):
    """Turn on Storage Locations, which internal transfers depend on.

    Odoo 17 passes the hook a ready environment; earlier versions passed (cr, registry).
    """
    multi_loc = env.ref('stock.group_stock_multi_locations', raise_if_not_found=False)
    base_user = env.ref('base.group_user', raise_if_not_found=False)
    if not multi_loc or not base_user:
        return
    if multi_loc not in base_user.implied_ids:
        base_user.write({'implied_ids': [(4, multi_loc.id)]})
    # Granting the group is not enough — mirror what the settings wizard does.
    warehouses = env['stock.warehouse'].with_context(active_test=True).search([])
    warehouses.int_type_id.active = True
```

```python
# __manifest__.py
'post_init_hook': 'post_init_hook',
```

Verify on a database created seconds ago, never on the working one:

```sql
SELECT code, active, count(*) FROM stock_picking_type GROUP BY 1,2 ORDER BY 1;
--  internal | f | 4     <-- archived warehouses, expected
--  internal | t | 2     <-- the live warehouses, now usable
```

## ⚠️ Pitfalls

- **Odoo 17 changed the hook signature.** It is now `post_init_hook(env)`; the old
  `post_init_hook(cr, registry)` fails the whole install with
  `TypeError: post_init_hook() missing 1 required positional argument: 'registry'`.
- `post_init_hook` runs on **install only**, not on `-u`. Re-running `-i` against a database
  where the module is already installed does not re-run it — you will chase a phantom.
  Always create a genuinely new database to test.
- `dropdb` fails silently while a connection is open, so the "fresh" database may be the old
  one. Confirm the drop, or use a new name each run.
- Archived records are invisible to `search()`. Whenever a lookup on standard Odoo data
  returns nothing unexpectedly, re-run it with `.with_context(active_test=False)` before
  assuming the record is absent.
- Keep the hook idempotent and defensive (`raise_if_not_found=False`): a hook that raises
  aborts the entire installation.

## Verification

```bash
createdb -h localhost -U odoo fresh_check
./odoo-bin -c odoo.conf -d fresh_check -i <modules> --stop-after-init
# then run the suite against that same database
./odoo-bin -c odoo.conf -d fresh_check -u <modules> --test-enable --stop-after-init
```

Do not run `-i` together with `--test-enable`: that also runs every core module's tests
(`web`, `http_routing`, …), which fail for unrelated environment reasons and bury the result.
Install first, then test with `-u`.

## References

- Related file: `security/noupdate-group-change-never-reaches-existing-databases.md`
- Related file: `models/undefined-ir-sequence-silently-names-every-record-new.md`
- Odoo source: `addons/stock/models/res_config_settings.py`
