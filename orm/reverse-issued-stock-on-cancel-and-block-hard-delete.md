# Reverse the Stock a Workflow Issued When It's Cancelled — and Block Hard-Delete of a Doc That Moved Stock

**Category:** ORM
**Tags:** #orm, #stock, #inventory, #workflow, #cancel, #unlink, #money, #integrity, #multi-company
**Severity:** 🔴 Critical
**Odoo Versions:** All

## Problem
A workflow step issues stock as a side effect — e.g. `work_order.action_complete()` validates
an internal transfer that moves material from the project store to the consumption/production
location (`action_issue_material`). Two integrity holes then open:

1. **Cancel only half-reverses.** `action_cancel` reverses the cost **journal entry**
   (`account_move._reverse_moves`) but leaves the **stock** consumed. The material is gone from
   the project store with the accounting undone — books and stock now disagree.
2. **Delete orphans the consumption.** The record can be `unlink()`-ed while completed; the
   validated pickings it created are **not** cascade-deleted (their `picking_id` link on the
   now-deleted line just vanishes), so the stock stays issued with **no document to explain
   it**. Observed live: 250 units left `WH/Project` via a work order whose picking had
   `origin='WO/…/00257'`, the work order was deleted, and the store sat at 0 with the 250
   stranded in `Virtual Locations/Production`.

## Solution ✅
**Reverse the stock on cancel, symmetrically to the journal:**
```python
def _return_issued_materials(self):
    self.ensure_one()
    prod_loc = self.env['project.material.issue']._production_location(self.company_id or self.env.company)
    for line in self.material_ids.filtered(lambda l: l.picking_id and l.picking_id.state == 'done'):
        dest = line.location_id or line.picking_id.location_id            # back to the project store
        ret = self.env['stock.picking'].create({
            'picking_type_id': <internal type for self.company_id>,
            'location_id': prod_loc.id, 'location_dest_id': dest.id, 'origin': _("Return: %s") % self.name,
            'move_ids_without_package': [(0, 0, {
                'name': _("Return of %s") % line.product_id.name, 'product_id': line.product_id.id,
                'product_uom': line.uom_id.id or line.product_id.uom_id.id, 'product_uom_qty': line.quantity,
                'location_id': prod_loc.id, 'location_dest_id': dest.id})],
        })
        ret.action_confirm(); ret.action_assign()
        for m in ret.move_ids:
            m.quantity = line.quantity; m.picked = True                   # force the done qty
        ret.with_context(skip_backorder=True, skip_sms=True).button_validate()
        line.picking_id = False

def action_cancel(self):
    for rec in self:
        rec._return_issued_materials()                                    # stock back first…
        if rec.account_move_id and rec.account_move_id.state == 'posted':
            rec.account_move_id._reverse_moves(cancel=True)               # …then reverse the books
        rec.write({'state': 'cancelled'})
```

**Block the hard delete — force the reversing path:**
```python
def unlink(self):
    for rec in self:
        if rec.state == 'completed' or rec.material_ids.filtered('picking_id'):
            raise UserError(_("You can't delete %s — it issued materials / posted costs. "
                              "Cancel it first (returns stock + reverses the entry), then delete.") % rec.display_name)
    return super().unlink()
```

## ⚠️ Pitfalls
- **Symmetry is the rule:** whatever a workflow step *creates* as a side effect (stock move,
  journal, sequence-numbered doc) its cancel path must *undo*. Reversing only the accounting is
  the classic half-fix — grep every side effect in the "do" method and mirror each in "cancel".
- **Don't cascade-delete the pickings; create a reverse transfer.** A validated `stock.move`
  represents real inventory history; deleting it corrupts valuation. The *return picking*
  (production → source) nets it out and keeps the audit trail.
- **Force the done quantity on the return.** The source (production) is a virtual location that
  may not "reserve"; set `move.quantity` + `move.picked = True` and
  `button_validate()` with `skip_backorder=True` so it validates without a wizard, instead of
  relying on `action_assign`.
- **Multi-company: never issue to a single global `stock.location_production`.** The picking's
  company must match its destination location's company, or you get
  `UserError: Incompatible companies`. Resolve the **work order's own company's** production
  location (its own, else a shared one) — a `env.ref('stock.location_production')` shortcut only
  works while everything is in the demo company. This bites in tests (the test DB has >1
  company) exactly as it would in a real multi-company deployment.
- **New fields ⇒ no migration:** the delete guard reads existing `state` / `picking_id`, so it
  applies immediately with no data change; existing already-orphaned stock must be corrected by
  hand in the UI (do NOT script inventory changes into a customer DB).

## Related
- `orm/amount-bound-override-authorization-for-a-hard-block.md` — same `action_complete` /
  cancel surface.
