# ⚠️ Domain Pitfall: Date Equality Constraints on Relational Fields

## Context
When filtering records in a relational field (e.g., `delivery_vehicle_id` on `stock.picking.batch`), a domain was applied to only show available vehicles for *today*: `[('operation_date', '=', context_today())]`.

## Problem ❌
If a user creates an "Available" vehicle for tomorrow, or if a batch is scheduled for a future date, the vehicle does not appear in the selection list. This causes confusion because the vehicle is objectively "Available", but hidden by the rigid date filter.

## Solution ✅
Avoid strict `context_today()` equality checks on domains when users might need to schedule or assign resources for future dates.

Instead of:
```xml
domain="[('state', 'in', ['available', 'assigned']), ('operation_date', '=', context_today())]"
```

Use a more permissive domain that allows the user to see all available resources, or one that properly compares against the record's target date (if applicable):
```xml
<!-- Best: just rely on the state, let the user pick the one they created -->
domain="[('state', 'in', ['available', 'assigned'])]"
```

## Odoo Versions
Tested on Odoo 15, 16, 17, 18, 19.

## Last Verified
2026-06-18
