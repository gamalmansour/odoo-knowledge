# Cross-Model Context Default Pollution on Core Models (purchase_order_project_id_fkey)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `context`, `default_get`, `foreign-key`, `purchase.order`, `stock.picking`, `sale.order`, `project_purchase`, `context-pollution`

---

## Problem

When navigating to a custom or inherited model from an action containing context defaults such as `default_project_id`, clicking any button or running logic that creates standard Odoo records (e.g. `purchase.order`, `stock.picking`, or `sale.order`) crashes with an opaque database constraint violation:

```
The operation cannot be completed: another model requires the record being deleted. If possible, archive it instead.

Model: Purchase Order (purchase.order)
Constraint: purchase_order_project_id_fkey
```

Or in Postgres server logs:
```
ERROR: insert or update on table "purchase_order" violates foreign key constraint "purchase_order_project_id_fkey"
DETAIL: Key (project_id)=(11) is not present in table "project_project".
```

## Root Cause

In Odoo, standard extension modules link core transaction models to standard projects (`project.project`):
- `project_purchase` adds `project_id = fields.Many2one('project.project')` to `purchase.order`.
- `project_stock` adds `project_id = fields.Many2one('project.project')` to `stock.picking`.
- `sale_project` adds `project_id = fields.Many2one('project.project')` to `sale.order`.

When an action opens a view with context like:
```python
context = {'default_project_id': self.id}  # where self is a custom project model e.g. construction.project
```
The active web client session carries `'default_project_id': <id>`.

When subsequent Python code calls:
```python
Purchase = self.env['purchase.order']
Purchase.create({...})
```
Odoo's ORM automatically inspects `self.env.context` for any key matching `default_<field_name>`. Because `purchase.order` has a field named `project_id`, Odoo automatically sets `vals['project_id'] = context['default_project_id']`. 

PostgreSQL checks the foreign key constraint `purchase_order_project_id_fkey` which references `project_project(id)`. Because the ID belongs to the custom table (`construction_project`), the constraint fails immediately. Odoo's error mapping in `sql_db.py` / `models.py` misinterprets any `_fkey` failure as a deletion conflict and displays *"another model requires the record being deleted"*.

## Solution ✅

Whenever instantiating or creating core records (`purchase.order`, `stock.picking`, `sale.order`) within contexts that might carry foreign default keys, explicitly sanitize the environment context:

```python
# 1. Sanitize context on model creation
safe_ctx = dict(self.env.context, default_project_id=False)
Purchase = self.env['purchase.order'].with_context(safe_ctx)
POLine = self.env['purchase.order.line'].with_context(safe_ctx)

po = Purchase.create({
    'partner_id': vendor.id,
    'origin': self.name,
    'company_id': self.company_id.id,
})
```

```python
# 2. When returning window actions to view the created records, sanitize context too:
def action_view_purchase_orders(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'name': _('Purchase Orders'),
        'res_model': 'purchase.order',
        'domain': [('id', 'in', self.purchase_order_ids.ids)],
        'view_mode': 'list,form',
        'context': dict(self.env.context, default_project_id=False, default_origin=self.name),
    }
```

## ⚠️ Pitfalls

1. **`dict(context).pop('default_project_id')` is not enough if parent context is re-merged:**
   Always explicitly pass `default_project_id=False` in `with_context(...)` so that any upstream context merge in ORM `default_get()` evaluates to `False`.
2. **Hidden in Stock & Sale too:**
   `stock.picking` (`stock_picking_project_id_fkey`) and `sale.order` (`sale_order_project_id_fkey`) are equally vulnerable whenever internal transfers or off-plan sales are generated from project screens.
3. **Unit Tests Often Miss This:**
   Standard unit tests that create records directly via `self.env['model'].create()` don't have web-client action contexts set. Always write tests that explicitly invoke methods under `with_context(default_project_id=999999)`.

## Verification

Run the requisition PO creation with an invalid foreign `default_project_id` in context:
```python
req = env['construction.material.requisition'].browse(req_id).with_context(default_project_id=999999)
po = req.action_create_purchase_order()
assert po, "PO must create successfully without foreign key violation"
```
