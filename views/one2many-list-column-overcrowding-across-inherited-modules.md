# One2many List Column Overcrowding Across Inherited Modules

- **Category:** Views / UI Ergonomics
- **Odoo Versions:** 17.0, 18.0, 19.0
- **Last Verified:** 2026-10-14

## Problem

When a core One2many `<list editable="bottom">` view (such as `requisition_line_ids` on `construction.material.requisition`) is extended by multiple downstream modules (`construction_project`, `construction_costcode`, `construction_requisition_stock`, `construction_requisition_budget`), each module often injects its own columns with `optional="show"` (or without `optional`).

In Odoo 17/18 (`web.ListRenderer`), having 14–16 visible columns in an inline One2many table causes severe horizontal compression:
- Column headers truncate into unreadable fragments (`L...`, `N..`, `Exemptio...`, `Unit of M...`, `On Hand (s...`, `Sho...`).
- Manual column-border dragging in the browser is **not persisted** across form reloads, forcing users to resize columns every time they open the form.
- Worse, if a downstream view replaces `decoration-danger` on `<list>` via `<attribute name="decoration-danger">is_over_qty or is_over_budget</attribute>`, it silently overwrites the base view's `decoration-danger="is_lcgpa_violation == True"`.

## Solution ✅

1. **Limit Default Visible Columns to 7–8 Core Operational Fields:**
   - Keep only the primary data-entry fields visible by default (`boq_item_id`, `product_id`, `stock_availability`, `qty`, `uom`, `requisition_type`, `unit_price`, `price_subtotal`).
   - Move all secondary, compliance, audit, and redundant stock-breakdown fields (`description`, `cost_code_id`, `qty_on_hand`, `shortfall_qty`, `is_over_qty`, `is_over_budget`, `is_lcgpa_mandatory`, `is_national_product`, `lcgpa_exemption_reason`, `lcgpa_exemption_ref`) to `optional="hide"`. Users can still toggle them on via the `⋮` optional-columns menu (which **is** persisted in browser `localStorage`).
2. **Use Concise Column Labels (`string="UoM"`):**
   - Override verbose field labels on narrow numeric/unit columns in the `<list>` view (e.g., `<field name="uom" string="UoM"/>`, `<field name="qty_on_hand" string="On Hand" optional="hide"/>`).
3. **Preserve Base Row Decorations When Inheriting `<list>` Attributes:**
   - When adding conditions to `decoration-danger` in an inherited module, combine the base condition rather than overwriting it:
     ```xml
     <xpath expr="//field[@name='requisition_line_ids']/list" position="attributes">
         <attribute name="decoration-danger">is_lcgpa_violation or is_over_qty or is_over_budget</attribute>
     </xpath>
     ```

## ⚠️ Pitfalls

- Never leave fields referenced in `<list decoration-danger="...">` out of the `<list>` children; use `optional="hide"` or `column_invisible="1"` so the web client still fetches their values for row evaluation.
- Note that if a user previously toggled optional columns in their browser for that specific view, Odoo's `localStorage` remembers their manual selection until reset from the `⋮` dropdown.
