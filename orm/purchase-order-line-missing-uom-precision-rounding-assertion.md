# Purchase Order Line Missing UoM Causes AssertionError in Float Precision Rounding

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19 (or "All")                  |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `purchase`, `stock`, `uom`, `precision_rounding`, `float_compare`, `onchange`

---

## Problem

When confirming a Purchase Order (`button_confirm()`) whose lines were created programmatically (e.g. from material requisitions, replenishment wizards, subcontracts, site requests, or data imports), the process crashes with an unhandled `AssertionError`:

```
Traceback (most recent call last):
  File "/odoo/addons/purchase/models/purchase_order.py", line 546, in button_confirm
    order.button_approve()
  File "/odoo/addons/purchase_stock/models/purchase_order.py", line 119, in button_approve
    self._create_picking()
  File "/odoo/addons/purchase_stock/models/purchase_order.py", line 298, in _create_picking
    moves = order.order_line._create_stock_moves(picking)
  File "/odoo/addons/purchase_stock/models/purchase_order_line.py", line 363, in _create_stock_moves
    for val in line._prepare_stock_moves(picking):
  File "/odoo/addons/sale_purchase_stock/models/purchase_order.py", line 26, in _prepare_stock_moves
    res = super()._prepare_stock_moves(picking)
  File "/odoo/addons/purchase_stock/models/purchase_order_line.py", line 251, in _prepare_stock_moves
    if float_compare(qty_to_attach, 0.0, precision_rounding=self.product_uom.rounding) > 0:
  File "/odoo/odoo/tools/float_utils.py", line 181, in float_compare
    rounding_factor = _float_check_precision(precision_digits=precision_digits,
  File "/odoo/odoo/tools/float_utils.py", line 35, in _float_check_precision
    assert precision_rounding > 0, "precision_rounding must be positive, got %r" % (precision_rounding,)
AssertionError: precision_rounding must be positive, got 0.0
```

## Root Cause

1. In standard Odoo `purchase.order.line`, the field `product_uom` is **not a computed field** and is **not required at the database level**. Instead, core Odoo relies on an `@api.onchange('product_id')` method to fill `product_uom` in web client form views.
2. When custom code or wizards create `purchase.order.line` records programmatically, `onchange` handlers do **not** run. If the calling code passes `product_uom: False` (or omits it), `product_uom` remains `NULL` (`False`) in the database.
3. This is further compounded when the source upstream model (e.g. `material.requisition.line`) also relied only on an `@api.onchange` to populate its own `uom` field, leaving records created via bulk import or wizard without a UoM (`line.uom = False`).
4. During `purchase_stock` order confirmation (`button_confirm` -> `button_approve` -> `_create_picking`), Odoo invokes:
   ```python
   float_compare(qty_to_attach, 0.0, precision_rounding=self.product_uom.rounding)
   ```
   On an empty recordset `self.product_uom` (`uom.uom()`), accessing `.rounding` returns the default float `0.0`.
5. In `float_utils.py`, `_float_check_precision` strictly asserts that `precision_rounding > 0`, crashing the entire transaction with `AssertionError: precision_rounding must be positive, got 0.0`.

## Solution ✅

Implement a 3-layer defensive architecture:

### 1. Fix the Upstream Source Model (Compute + Precompute)
Never rely solely on `@api.onchange` for source line UoMs. Make `uom` a stored computed field with `readonly=False` and `precompute=True`, plus a fallback inside `create()`:

```python
class MaterialRequisitionLine(models.Model):
    _name = 'construction.material.requisition.line'

    uom = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        compute='_compute_uom',
        store=True,
        readonly=False,
        precompute=True,
    )

    @api.depends('product_id')
    def _compute_uom(self):
        for line in self:
            if line.product_id and not line.uom:
                line.uom = line.product_id.uom_po_id or line.product_id.uom_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('uom') and vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                if product.exists():
                    vals['uom'] = (product.uom_po_id or product.uom_id).id
        return super().create(vals_list)
```

### 2. Multi-Tier Fallback in PO Generation Wizards/Actions
When generating `purchase.order.line` dicts from any custom module, fall back gracefully across `uom`, `uom_po_id`, and `uom_id`:

```python
line_uom = line.uom or line.product_id.uom_po_id or line.product_id.uom_id
po_line_vals = {
    'product_id': line.product_id.id,
    'product_uom': line_uom.id if line_uom else False,
    'product_qty': line.qty,
    # ...
}
```

### 3. Downstream Global Fail-Safe on `purchase.order.line`
Inherit `purchase.order.line` in a foundational module (such as `construction_costcode` or a core company extension) to guarantee that any PO line created anywhere in the system without `product_uom` automatically gets assigned the product's purchase or base UoM:

```python
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('product_uom') and vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                if product.exists():
                    uom = product.uom_po_id or product.uom_id
                    if uom:
                        vals['product_uom'] = uom.id
        return super().create(vals_list)
```

### 4. Database Data Healing
Heal any legacy database records that already have `NULL` UoMs before running confirmation:

```sql
UPDATE purchase_order_line pol
SET product_uom = COALESCE(pt.uom_po_id, pt.uom_id)
FROM product_product pp
JOIN product_template pt ON pp.product_tmpl_id = pt.id
WHERE pol.product_id = pp.id AND pol.product_uom IS NULL;

UPDATE construction_material_requisition_line rl
SET uom = COALESCE(pt.uom_po_id, pt.uom_id)
FROM product_product pp
JOIN product_template pt ON pp.product_tmpl_id = pt.id
WHERE rl.product_id = pp.id AND rl.uom IS NULL;
```

## ⚠️ Pitfalls

- **Do NOT assume Odoo core fields are DB required**: Even though `product_uom` is required in the PO form UI (`<field name="product_uom" .../>`), Odoo ORM allows programmatic records with `product_uom=False` if `required=True` is not set on the Python model definition.
- **`onchange` is UI-only**: Methods decorated with `@api.onchange` never trigger on `model.create()` or `model.write()` called from code, background jobs, wizards, or EDI/APIs.
- **Empty recordset attribute evaluation**: In Python/Odoo, accessing an attribute on an empty recordset (e.g. `self.env['uom.uom'].browse().rounding`) returns `0.0` or `False`, never raising `AttributeError` or `ValueError`. This turns silent data anomalies into late runtime crashes deep inside core stock code.

## Verification

Run automated tests creating both requisition-generated POs and direct PO lines without explicit UoM:

```bash
python odoo-bin -c odoo.conf -d db_name --test-enable --test-tags=/construction_material_requisition:TestRequisitionUomAndPoConfirmation --stop-after-init
```

Ensure all POs can execute `button_confirm()` cleanly and generate incoming pickings without triggering `AssertionError`.

## References

- Odoo Core: `addons/purchase_stock/models/purchase_order_line.py`
- Odoo Float Utils: `odoo/tools/float_utils.py`
- Related KB entry: `orm/onchange-only-computation-breaks-nonform-create.md`
