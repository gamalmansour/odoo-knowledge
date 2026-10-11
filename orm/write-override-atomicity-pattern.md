# write() Override — State Changes Must Come AFTER super().write()

| Field         | Value                          |
|---------------|--------------------------------|
| Category      | orm                            |
| Odoo Versions | All (14, 15, 16, 17, 18, 19)  |
| Severity      | 🔴 Critical                    |
| Last Verified | 2026-06-27                     |
| Author        | ENG/Gamal Mansour              |

**Tags:** `write`, `override`, `atomicity`, `state-machine`, `transaction`

---

## Problem

When overriding `write()`, changing state on related records **before** calling `super().write()` can cause data corruption if the DB write fails:

```python
# ❌ WRONG — state changed before write, not atomic
def write(self, vals):
    if 'vehicle_id' in vals:
        vehicle = self.env['delivery.vehicle'].browse(vals['vehicle_id'])
        vehicle.state = 'assigned'   # ← happens even if write() fails below!

    return super().write(vals)       # ← if this raises, vehicle.state is corrupt
```

If `super().write()` fails (e.g. SQL constraint violation, concurrent update), the vehicle state has already been modified with no rollback.

## Root Cause

Odoo's ORM runs inside a database transaction, but Python-level code that mutates other records **before** the main write is not automatically rolled back if an exception occurs later in the same method. The DB itself will rollback, but only if the exception propagates to the top-level transaction boundary.

In practice, partial state corruption can happen when `super().write()` raises a `UserError` or `ValidationError` that is caught somewhere in the call stack.

## Solution ✅

Always perform side-effect state changes **after** `super().write()`:

```python
# ✅ CORRECT — all state changes happen after the write succeeds
def write(self, vals: dict) -> bool:
    """Sync related model state after successful write."""
    res = super().write(vals)  # ← DB write happens first

    # State changes here — only reached if super() succeeded
    if 'vehicle_id' in vals and vals['vehicle_id']:
        vehicle = self.env['delivery.vehicle'].browse(vals['vehicle_id'])
        if vehicle.state == 'available':
            vehicle.state = 'assigned'

    if 'state' in vals and vals['state'] == 'done':
        for record in self:
            # update related records...
            pass

    return res
```

## ⚠️ Pitfalls

- If you need the **old** value of a field before the write, capture it before `super()`:
  ```python
  old_states = {r.id: r.state for r in self}
  res = super().write(vals)
  # use old_states[r.id] after super()
  ```
- Don't confuse this with `create()` — in `create()`, `super()` must come first by definition.
- This pattern applies equally to `unlink()` overrides.

## Verification

Write a test that triggers a `_sql_constraints` violation in `super().write()` and verify that no side-effect state changes occurred on related records.

## Extended Pattern — Action Methods (not just write())

The same rule applies to **any action method** that triggers financial or stock operations. A common anti-pattern in wizard/button actions:

```python
# ❌ WRONG — state set before risky operations
def action_end_visit(self):
    for visit in self:
        visit.state = 'done'          # ← set first
        visit.check_out = now
        visit._validate_delivery_picking()   # ← if this raises silently...
        visit._create_return_credit_note()   # ← ...or this fails quietly
        visit._create_collection_payments()  # ← visit is already 'done' with no records!
```

```python
# ✅ CORRECT — state set last, exceptions propagate
def action_end_visit(self):
    for visit in self:
        visit._validate_delivery_picking()   # raises UserError on failure
        visit._create_return_credit_note()   # raises on failure
        visit._create_collection_payments()  # raises on failure
        # Only reached if ALL above succeeded
        visit.state = 'done'
        visit.check_out = fields.Datetime.now()
```

Also ensure helper methods do NOT swallow exceptions with `except Exception: _logger.error(...)`. They must let exceptions propagate so the transaction rolls back and the user sees a clear error message.

## References

- Fixed in: `custom/delivery_vehicle/models/stock_picking_batch.py` — `action_generate_load_transfer` button_validate silent failure (2026-06-27)
- Fixed in: `custom/sale_visit/models/sale_visit.py` — `action_end_visit` + `_validate_delivery_picking` + `_create_return_credit_note` + `_create_collection_payments` (2026-06-27)
