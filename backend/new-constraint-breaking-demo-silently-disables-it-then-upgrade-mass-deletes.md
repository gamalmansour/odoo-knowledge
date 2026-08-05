# A New Constraint That Breaks Demo Data Silently Disables It — Then the Next Upgrade Mass-Deletes

| Field         | Value        |
|---------------|--------------|
| Category      | backend      |
| Odoo Versions | 16, 17, 18   |
| Severity      | 🔴 Critical  |
| Last Verified | 2026-08-05   |
| Author        | ENG/Gamal Mansour |

**Tags:** `api.constrains`, `demo-data`, `_process_end`, `ir.model.data`, `upgrade`, `unlink`

---

## Problem

Adding an innocent-looking `@api.constrains` and upgrading twice produced a registry that
would not load at all:

```
odoo.addons.base.models.ir_model: Deleting 16@project.work.order (construction_project.wo_16)
...
UserError: You can't delete work order WO-5-17 — it has issued materials and/or posted costs.
CRITICAL odoo.service.server: Failed to initialize database
```

The second upgrade was trying to **delete demo work orders**, an unlink guard rightly
refused, and the whole database became unloadable. Nothing in the constraint mentioned
demo data, and the first upgrade had reported only test failures.

## Root Cause

A three-step cascade, each step silent or nearly so:

1. **The new constraint fired against existing demo data.** The constraint forbade labor
   lines on completed work orders; `demo_wo_costs.xml` legitimately creates exactly that
   (historical records are born completed with their cost lines). On upgrade, demo XML is
   re-loaded and `_validate_fields` raised.

2. **Odoo does not fail an upgrade over demo data — it flips the module's `demo` flag off
   and moves on.** The only trace is a warning buried mid-log. The module is now
   permanently "demo-less" in `ir_module_module.demo`, and dependent modules follow.

3. **The next upgrade sees every demo xml_id as an orphan.** With demo off, the demo files
   are not read, so none of their `ir.model.data` rows are re-encountered, and
   `_process_end` — whose job is deleting records removed from source — tries to unlink
   every demo record of the module. Any unlink guard (and money-bearing models should have
   them) turns that into a fatal registry failure.

## Solution ✅

Two independent fixes, both needed:

**1. Scope the constraint to the vector it actually guards.** The business rule was "a
daily-sheet line must not charge a completed order", not "no labor line may ever reference
a completed order" — historical imports create completed orders *with* their lines in one
call, and demo data is precisely such an import:

```python
@api.constrains('work_order_id')
def _check_sheet_line_work_order_open(self):
    for rec in self:
        if (rec.labor_sheet_id and rec.work_order_id            # sheet lines only
                and rec.work_order_id.state in ('completed', 'cancelled')):
            raise ValidationError(...)
```

**2. Restore the demo flags the failure already flipped** (source fix alone does not heal
the database):

```sql
UPDATE ir_module_module SET demo=true
WHERE state='installed' AND name IN (<modules whose manifest has a 'demo' key>);
```

Derive the list from the manifests, not from memory — dependent modules were flipped too
(21 of them here, from one constraint).

## ⚠️ Pitfalls

- **Before adding any constraint, run it mentally against the demo data** — demo records
  are the one dataset guaranteed to be re-validated on every upgrade of the module. If the
  demo has a record the new rule forbids, either the rule is too broad (as here) or the
  demo needs updating in the same commit.
- The "1 failed, N errors" of the first upgrade hides the real event. Grep for
  `demo` + `Failed` or check `SELECT name FROM ir_module_module WHERE demo=false` against
  the manifests when anything smells off after adding constraints.
- The mass-delete happens on the *second* upgrade, far from the cause — the constraint
  may even have been fixed in between, which makes the delete look spontaneous.
- An unlink guard raising `UserError` during `_process_end` kills registry loading for
  every user. Guards are still right — the alternative is silent data loss.
- `@api.constrains` runs via `_validate_fields` on XML load too, not only on user writes;
  "demo data loaded before the constraint existed" is no protection on re-load.

## Verification

```bash
# after the fix, both must hold:
./odoo-bin -d <db> -u <modules> --stop-after-init        # loads, no Deleting .. demo ids
psql -c "SELECT count(*) FROM ir_module_module
         WHERE demo=false AND state='installed' AND name IN (<demo-shipping modules>);"
# -> 0
```

## References

- Related file: `backend/assertraises-savepoint-rolls-back-pre-raise-writes.md`
- Related file: `models/undefined-ir-sequence-silently-names-every-record-new.md`
- Odoo source: `odoo/addons/base/models/ir_model.py` (`_process_end_unlink_record`)
