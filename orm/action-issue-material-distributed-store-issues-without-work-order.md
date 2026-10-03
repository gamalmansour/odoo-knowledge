# 📦 Action Issue Material Must Defensively Support Distributed Store Issues (Without Work Order)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `stock`, `stock.picking`, `material-issue`, `store-issue`, `work-order`, `multi-company`

---

## Problem

When materials are issued via the distributed data-entry model using **Store Material Issue notes** (`construction.store.issue`), the material lines (`project.material.issue`) intentionally leave `work_order_id` empty (`work_order_id = False`).
If the underlying `action_issue_material()` method blindly dereferences `rec.work_order_id.company_id.id` to create the `stock.picking` internal transfer:
```python
picking_type = self.env['stock.picking.type'].search([
    ('code', '=', 'internal'), ('company_id', '=', rec.work_order_id.company_id.id)
], limit=1)
if not picking_type:
    raise UserError(_("No internal transfer operation type found for company %s.") % rec.work_order_id.company_id.name)
```
The search evaluates against `('company_id', '=', False)` and immediately raises:
`UserError: No internal transfer operation type found for company False.`

## Root Cause

`action_issue_material` was originally authored assuming material consumption always occurs inside a site engineer's Work Order. When the distributed storekeeper module (`construction_store_issue`) was added, it reused `project.material.issue` lines with `issue_note_id` while leaving `work_order_id` unset. Any direct attribute access to `work_order_id` (such as `.company_id`, `.name`, or `.boq_item_id`) collapses to `False`.

## Solution ✅

Defensively resolve company, picking origin, and BOQ item from the available relational chain before attempting stock move operations:

```python
def action_issue_material(self):
    for rec in self:
        if rec.picking_id or not rec.product_id.is_storable:
            continue
        if not rec.location_id:
            raise UserError(_("Please set a source location for stockable material %s.") % rec.product_id.name)
        
        # 1. Defensively resolve company from WO, Project, Location, or Env
        company = rec.work_order_id.company_id or rec.project_id.company_id or rec.location_id.company_id or self.env.company
        production_location = rec._production_location(company)
        if not production_location:
            raise UserError(_("No production/consumption location found. Please configure one in Inventory settings."))

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'), ('company_id', '=', company.id)
        ], limit=1)
        if not picking_type:
            raise UserError(_("No internal transfer operation type found for company %s.") % company.name)
        
        # 2. Defensively resolve origin and BOQ item
        origin = rec.work_order_id.name or (getattr(rec, 'issue_note_id', False) and rec.issue_note_id.name) or rec.project_id.name or _('Material Issue')
        boq_item_id = (rec.work_order_id.boq_item_id.id if rec.work_order_id else False) or (rec.boq_target_id.id if rec.boq_target_id else False)

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': rec.location_id.id,
            'location_dest_id': production_location.id,
            'origin': origin,
            'company_id': company.id,
            'boq_item_id': boq_item_id,
            'move_ids_without_package': [(0, 0, {
                'name': rec.product_id.name,
                'product_id': rec.product_id.id,
                'product_uom_qty': rec.quantity,
                'product_uom': (rec.uom_id or rec.product_id.uom_id).id,
                'location_id': rec.location_id.id,
                'location_dest_id': production_location.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
```

## ⚠️ Pitfalls

- **Do NOT assume `work_order_id` is always populated:** In decentralized site operations (distributed data-entry), material issues and daily labor sheets are captured at their source (store / gate) without a work order.
- **PostgreSQL Column Default on Inherited Models:** If an addon (`construction_waste`) adds a `required=True` column (e.g. `consumption_type`) to a model, ensure PostgreSQL has a server-side default (`ALTER TABLE ... SET DEFAULT 'permanent'`) so unlinked sibling modules running in partial isolation don't violate NOT NULL constraints.

## Verification

Run store issue note confirmation in shell:
```python
note = env['construction.store.issue'].create({...})
note.action_issue()
assert note.state == 'issued'
assert all(note.line_ids.mapped('is_cost_confirmed'))
```
