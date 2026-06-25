# Product Costing and Inventory Valuation in Multi-Warehouse Setup

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-06-25                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `stock`, `costing`, `avco`, `fifo`, `multi-warehouse`, `landed-costs`

---

## Problem

In standard Odoo, when a company has multiple warehouses (e.g., Alexandria and Aswan) and uses the **Average Cost (AVCO)** costing method, applying transportation or shipping costs (Landed Costs) to internal transfers to a specific warehouse distorts the valuation of inventory in *all* warehouses. 

For example:
1. Product cost at receipt in Alexandria = 130 EGP.
2. Transfer to Aswan incurs a transport cost of 10 EGP per unit.
3. If Landed Cost is applied to the internal transfer, the 10 EGP is added to the product's overall valuation.
4. Because AVCO is calculated globally, the system-wide average cost rises to 135 EGP.
5. Consequently, the inventory in Alexandria is overvalued (135 instead of 130 EGP), and the inventory in Aswan is undervalued (135 instead of 140 EGP).

## Root Cause

Odoo's standard costing engine tracks the product cost (`standard_price` field on `product.product` / `product.template`) at the **Company level** (`company_dependent=True`), not at the **Warehouse/Location level**. 

Under AVCO, any value adjustments (like Landed Costs) are distributed across the total quantity of the product company-wide, recalculating a single global average cost.

## Solution ✅

There are two primary ways to resolve this in Odoo:

### Method 1: Using FIFO (First In First Out / Real Cost) (Standard Odoo)
Change the costing method of the Product Category to **FIFO** and set Inventory Valuation to **Automated**.

1. Go to **Inventory > Configuration > Product Categories**.
2. Select or create the category for the products.
3. Set **Costing Method** to `First In First Out (FIFO)`.
4. Set **Inventory Valuation** to `Automated`.
5. Under FIFO, Odoo creates individual **Stock Valuation Layers (SVL)** (`stock.valuation.layer`) for each transfer.
6. When Landed Cost is applied to an Internal Transfer, it updates only the SVL layer associated with the destination warehouse. 
7. The Inventory Valuation report grouped by Location will correctly show:
   - Alexandria inventory valued at 130 EGP/unit.
   - Aswan inventory valued at 140 EGP/unit.

### Method 2: Custom Module for Warehouse-specific Costing
If AVCO is business-mandatory, use a custom module (e.g., `product_cost_per_warehouse` or `stock_valuation_by_location` from Odoo App Store) to compute separate average costs per warehouse.

These modules modify the `standard_price` calculation to group by warehouse/location instead of company.

## ⚠️ Pitfalls

- **AVCO standard_price Reference:** Even under FIFO, the `standard_price` shown on the product form represents the cost of the *next* outgoing layer or a weighted average. Always rely on **Inventory Valuation Reports** or the **Stock Valuation Layers** table for true location-based costing rather than the product card price.
- **Landed Cost on Internal Transfers:** Ensure that Landed Costs are correctly configured to apply to Internal Transfers (`stock.picking` of type internal).

## References

- [Odoo Inventory Valuation Documentation](https://www.odoo.com/documentation/17.0/applications/inventory_and_mrp/inventory/management/reporting/valuation_methods.html)
- Related: `views/print-ready-a4-css-layouts.md`
