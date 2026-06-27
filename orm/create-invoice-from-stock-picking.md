# Creating Invoices from Stock Pickings (Delivery Orders)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🟢 Low                                     |
| Last Verified | 2026-06-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `stock.picking`, `sale.order`, `account.move`, `invoicing`

---

## Problem

A supervisor or salesperson needs to trigger invoice creation directly from a stock picking (Delivery Order) once it is validated, without navigating back to the Sale Order.

## Root Cause

In standard Odoo, invoices are generated from Sale Orders using a wizard or from the list view. There is no native button on `stock.picking` to invoke invoicing for the related Sale Order.

## Solution ✅

Inherit `stock.picking`, add a related field to track the invoicing status of the associated sale order, and define a method to call `_create_invoices()` on the sale order under `sudo()`.

### Python Model Inheriting `stock.picking`

```python
# models/stock_picking.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sale_invoice_status = fields.Selection(
        related='sale_id.invoice_status',
        string='Sale Invoice Status'
    )

    def action_create_sale_order_invoice(self) -> dict:
        self.ensure_one()
        if not self.sale_id:
            raise UserError(_("This stock picking is not linked to any Sale Order."))

        sale_order = self.sale_id

        # Safeguard: check invoice status
        if sale_order.invoice_status == 'invoiced':
            raise UserError(_("The related Sale Order %s is already fully invoiced.") % sale_order.name)
        elif sale_order.invoice_status == 'no':
            raise UserError(_("The related Sale Order %s has no lines to invoice.") % sale_order.name)

        # Run under sudo to bypass billing access limitations for representatives/supervisors
        invoices = sale_order.sudo()._create_invoices()
        
        if not invoices:
            raise UserError(_("No invoice could be created."))

        # Log to chatters
        message = _("Invoice %s created from Stock Picking %s.") % (", ".join(invoices.mapped('name')), self.name)
        self.message_post(body=message)
        sale_order.message_post(body=message)

        # Open the invoice view
        return sale_order.action_view_invoice(invoices)
```

### XML Form View Button

```xml
<xpath expr="//header" position="inside">
    <button name="action_create_sale_order_invoice" 
            string="Create Invoice" 
            type="object" 
            class="btn-primary" 
            invisible="not sale_id or state != 'done' or sale_invoice_status in ('invoiced', 'no')"/>
</xpath>
```

## ⚠️ Pitfalls

- **Access Rights**: Stock managers/representatives might not have invoice creation permissions. Always invoke `_create_invoices()` using `.sudo()` if the action is meant to be triggered by non-billing users.
- **Invoicing Policy**: If the invoicing policy on sale order lines is "Delivered quantities", the picking must be in `'done'` state (validated) before any lines become invoiceable.

## Verification

Validate the picking first, then click "Create Invoice". It will trigger invoice generation and open the form view of the created invoice.
