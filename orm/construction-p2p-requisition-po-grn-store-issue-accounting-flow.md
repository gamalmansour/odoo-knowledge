# Construction Material Requisition Full P2P & Site Consumption Accounting Cycle

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `p2p`, `material-requisition`, `purchase`, `stock-picking`, `vendor-bill`, `store-issue`, `accounting`, `boq`, `odoo18`

---

## Problem

When testing or deploying the end-to-end Material Requisition lifecycle (`construction.material.requisition`) through automated procurement and warehouse issuance to construction sites:

1. **Vendor Selection Trap on Requisition Confirmation**: Calling `action_create_purchase_order()` fails with:
   ```text
   UserError: There is no vendor configured for product [MAT-SND-WSH] Washed Sand for Mortar & Screed.
   ```
2. **Dual Inventory Accounting Paradigm in Odoo 18**: If products have `is_storable = False` (consumables/direct site deliveries), Odoo 18 skips Stock Interim accounts and posts costs directly to Direct Project Costs upon Vendor Bill validation. If `is_storable = True`, real-time perpetual inventory entries are required (`103001` Stock Valuation / `103002` Stock Interim Received / `400085` Direct Project Cost).
3. **Store Issue Stock Shortage**: Requisition internal lines fulfilled via Store Issue Notes (`construction.store.issue`) fail on validation if `WH/Stock` has zero on-hand quantity, raising:
   ```text
   UserError: Insufficient stock of ... at WH/Stock to issue ... Transfer or purchase the material to the project location first.
   ```

---

## Root Cause

1. **Missing `product.supplierinfo`**: `mr.action_create_purchase_order()` uses `line.product_id._select_seller()` to group requisition lines by vendor and populate `purchase.order` headers. If no active vendor pricing rule exists for the product, PO creation is blocked.
2. **Odoo 18 Storable Product Paradigm**: Odoo 18 introduced `is_storable` on products. When `is_storable = False`, `stock.move._account_entry_move()` returns empty, because consumable goods are expensed at billing time rather than inventory receipt.
3. **Decoupled Site Store Issue Architecture**: Store Issue Notes (`construction.store.issue`) implement the distributed site data-entry model where lines (`project.material.issue`) do not require a Work Order, but directly deduct physical stock from `rec.location_id` into the project consumption location. When stock is not physically on-hand, `action_assign()` fails.

---

## Solution ✅

### 1. Configure Vendor Information on Purchasable Products
Ensure purchasable products have a valid vendor entry before triggering PO generation:
```python
supplier_info = env['product.supplierinfo'].search([
    ('product_tmpl_id', '=', product.product_tmpl_id.id),
    ('partner_id', '=', vendor.id),
], limit=1)
if not supplier_info:
    env['product.supplierinfo'].create({
        ('product_tmpl_id'): product.product_tmpl_id.id,
        ('partner_id'): vendor.id,
        ('price'): unit_price,
        ('min_qty'): 1.0,
        ('delay'): 1,
    })
```

### 2. Standardized Dual Accounting Flows

#### Flow A: Direct Site Purchase / Consumable Delivery (`is_storable = False`)
- **PO Creation & Confirmation**: `P00001` confirmed.
- **Goods Receipt (GRN)**: `WH/IN/00001` validated (updates inventory quantities and creates SVL for audit without interim accounting moves).
- **Vendor Bill (`in_invoice`)**:
  - **Debit**: `400085` تكاليف ومصروفات مواد المشروعات (Direct Project Materials Cost)
  - **Credit**: `201002` موردون محليون (Accounts Payable)

#### Flow B: Central Warehouse Stock & Project Site Issue (`is_storable = True` Real-Time Valuation)
- **Goods Receipt (GRN)**:
  - **Debit**: `103001` مخزون الخامات ومواد البناء (Stock Valuation)
  - **Credit**: `103002` وسيط استلام المخزون (Stock Interim Received)
- **Vendor Bill (`in_invoice`)**:
  - **Debit**: `103002` وسيط استلام المخزون (Stock Interim Received)
  - **Credit**: `201002` موردون محليون (Accounts Payable)
- **Store Issue Note (`construction.store.issue`)**:
  - **Debit**: `400085` تكاليف ومصروفات مواد المشروعات (Direct Project Materials Cost)
  - **Credit**: `103001` مخزون الخامات ومواد البناء (Stock Valuation)

### 3. Fulfilling Requisition Internal Lines & Site Issue
1. Create and confirm Store Issue Note:
```python
issue_note = env['construction.store.issue'].create({
    'project_id': project.id,
    'location_id': warehouse.lot_stock_id.id,
    'cost_code_id': cost_code.id,
    'line_ids': [(0, 0, {
        'product_id': line.product_id.id,
        'quantity': line.quantity,
        'uom_id': line.uom_id.id,
        'project_id': project.id,
        'boq_item_id': boq_item.id,
        'cost_code_id': cost_code.id,
    }) for line in mr.requisition_line_ids],
})
issue_note.action_issue()
```
2. Update Material Requisition state upon completion:
```python
mr.write({'state': 'receive'})
```

---

## ⚠️ Pitfalls

- **Do NOT attempt to toggle `is_storable` on products after stock moves exist**: Odoo raises `UserError: You cannot change the inventory tracking of a product that was already used`. Configure the product type correctly from inception.
- **`company_ids` vs `company_id` in Odoo 18 Accounting**: `account.account` in Odoo 18 uses `company_ids` (Many2many). Searching on `account.account` must use `[('code', '=', '103001'), ('company_ids', 'in', company.id)]`.
- **BOQ Cost Confirmation**: Ensure `is_cost_confirmed` computes to `True` when `issue_note_id.state == 'issued'`, so that project analytics and actual vs. budgeted cost reports capture the consumption immediately.

---

## Verification

Run Odoo Shell:
```python
mr = env['construction.material.requisition'].search([('name', '=', 'MR/2026/00010')])
assert mr.state == 'receive'
po = env['purchase.order'].search([('origin', 'ilike', mr.name)])
assert po and po.state == 'done'
bills = po.invoice_ids.filtered(lambda b: b.state == 'posted')
assert bills
store_issues = env['construction.store.issue'].search([('project_id', '=', mr.project_id.id), ('state', '=', 'issued')])
assert store_issues
```

---

## References

- Related: `orm/action-issue-material-distributed-store-issues-without-work-order.md`
- Related: `orm/subcontract-progress-invoice-unit-price-and-boq-actual-cost.md`
- Related: `orm/receivable-payable-account-move-line-due-date-constraint.md`
