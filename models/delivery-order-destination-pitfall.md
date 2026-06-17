# ⚠️ Delivery Pitfall: Changing `location_dest_id` of Customer Delivery Order

## Context
When loading goods into a delivery vehicle using a `stock.picking.batch`, there is a temptation to dynamically change the `location_dest_id` of all the pickings in the batch to match the vehicle's `location_id` (Staging/Transit location).

## Problem ❌
If you change the `location_dest_id` of a customer delivery order (`OUT`) to an internal transit location (like the vehicle's location):
1. The goods leave the warehouse but **never reach the customer system-wise**.
2. They get stuck in the vehicle's location permanently (unless manually moved).
3. The Sales Order remains "undelivered" and cannot be fully invoiced because the goods haven't reached a `Customer Location`.

## Solution ✅ (2-Step Delivery / Cross-Docking)
Never change the `location_dest_id` of a Customer Delivery Order to an internal location. Instead:
1. **Change the `location_id` (Source Location):** Update the customer delivery order to take goods *from* the vehicle (`vehicle_id.location_id`).
2. **Create an Internal Transfer (Load Transfer):** Generate a separate `Internal Transfer` picking that moves the aggregated goods from the `Warehouse/Stock` to the `vehicle_id.location_id`.
3. **Validate Sequence:** 
   - First validate the Internal Transfer to physically load the vehicle.
   - Then validate the Delivery Orders (via Portal Visits or manually) to move the goods from the vehicle to the customer.

## Odoo Versions
Applies to all modern Odoo versions (15, 16, 17, 18, 19).

## Last Verified
2026-06-18
