# Partner-Level vs Company-Level Constraints in Visits

## Context
When designing sales or merchandising visit constraints (such as `max_zero_shelf_lines` or `max_zero_warehouse_lines`), the initial instinct is often to place these settings at the `res.company` or `res.config.settings` level. 

## Problem
If constraints are set globally (e.g., allowing 2 zero-quantity products company-wide), it creates a loophole for customers who have a very small range of "usual products". If a customer only has 2 usual products, a company-wide allowance of 2 means the representative can skip checking inventory entirely for that customer without triggering a validation error.

## Solution ✅
Move business constraints that are tightly coupled with the product count directly to the `res.partner` level.
1. Define the fields on `res.partner` (or a related partner-specific model).
2. Allow the sales administrator to specify the allowed zeros *per customer* depending on the size of that customer's usual product list.
3. Update validation logic in `sale.visit` (e.g., in `action_end_visit`) to read constraints from `visit.partner_id` instead of `visit.company_id`.

## ⚠️ Pitfalls
- Forgetting to migrate existing data or remove the old fields from `res.company`, leaving dead fields in the settings view.
- Not adding the fields to the `res.partner` view (like the `Usual Products` tab).

**Last Verified:** 2026-06-12
