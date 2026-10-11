# State-gated workflow button that must be re-run — widen the states AND make the action idempotent

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-09                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `views`, `state-machine`, `idempotency`, `stock`, `purchase`, `double-buy`, `money`

---

## Problem

A workflow action button is gated to a single state, e.g.:

```xml
<button name="action_smart_route" string="Check Stock &amp; Route" type="object"
        invisible="state != 'approve'"/>
```

The action itself advances the state when it runs (`approve` → `stock`). So after the
first click the button **disappears** and the user can never run it again — even though
the process legitimately loops back and needs it. Concretely: a material requisition
routes on-hand stock via internal transfer and raises a PO for the shortfall; after the
PO is **received into the main warehouse** the material still has to be transferred to
the project/site location, which means running the same routing action again — but the
button is gone.

## Root Cause

Two coupled mistakes:
1. **Visibility gated to one state** while the underlying step is legitimately repeatable
   across several states (approved → PO created → received).
2. **The action is not idempotent.** It recomputes from *current* on-hand each call with
   no memory of what it already transferred/ordered. So simply widening the visibility
   would let a second click **double-transfer** stock or **double-buy** on a new PO — a
   directional money leak (see also [[money-flow-reversal-on-refund-cancel-reset-draft]]).

## Solution ✅

Fix BOTH sides together — never widen the button without hardening the action.

1. Widen the button to every state where the step is meaningfully re-runnable:

```xml
<button name="action_smart_route" string="Check Stock &amp; Route" type="object"
        invisible="state not in ('approve', 'stock', 'receive')"/>
```

2. Make the action net against work already done, so re-running only handles the
   outstanding remainder:

```python
transferred_left = {}
for mv in self.internal_picking_ids.filtered(lambda p: p.state != 'cancel').move_ids:
    transferred_left[mv.product_id.id] = transferred_left.get(mv.product_id.id, 0.0) + mv.product_uom_qty
ordered_left = {}
for po in self.purchase_order_ids.filtered(lambda p: p.state != 'cancel'):
    for pol in po.order_line:
        ordered_left[pol.product_id.id] = ordered_left.get(pol.product_id.id, 0.0) + pol.product_qty

for line in self.requisition_line_ids:
    pid = line.product_id.id
    already_transferred = min(transferred_left.get(pid, 0.0), line.qty)
    transferred_left[pid] -= already_transferred
    outstanding = line.qty - already_transferred        # skip if <= 0
    available = min(line.qty_on_hand, outstanding)       # transfer this now
    shortfall = outstanding - available
    already_ordered = min(ordered_left.get(pid, 0.0), shortfall)
    ordered_left[pid] -= already_ordered
    to_purchase = shortfall - already_ordered            # PO only what's not on an open PO
```

Net effect: 1st run buys the shortfall, 2nd run (after receipt) transfers the arrived
stock to site with **no new PO**, 3rd accidental run is a **no-op**.

## ⚠️ Pitfalls

- Filter out `state == 'cancel'` pickings and POs when counting already-done qty, or a
  cancelled transfer wrongly suppresses a needed re-transfer.
- Keep a running per-product remainder (`... -= consumed`) so the same product on two
  lines isn't double-discounted.
- Changing an inherited **form view** (`ir.ui.view` arch) needs a module upgrade
  (`-u <module>`) to reach the DB — `--dev=xml` alone does NOT reload non-QWeb view arch.
- Bump the module `version` when behaviour changes so environments actually re-upgrade.

## Verification

```bash
python -m py_compile <module>/models/*.py
odoo-bin -c conf -d <db> -u <module> --no-http --stop-after-init   # exit 0, no traceback
```
Then in the UI: approve → route (PO for shortfall) → receive PO to main store →
button still visible → route again → internal transfer to site created, no second PO →
route once more → "Nothing to route".

## References

- Related file: `orm/independent-control-policies-not-one-guard.md`
- Related file: `orm/money-flow-reversal-on-refund-cancel-reset-draft.md`
