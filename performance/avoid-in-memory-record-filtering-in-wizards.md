# Avoid In-Memory Record Filtering in Wizards and Search Actions

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | performance                                |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `performance`, `memory-leak`, `filtered`, `orm`, `wizard`

---

## Problem

When writing wizards or report actions to show "unscheduled" or "missing" records, developers often fetch all target records in memory and then filter them using Python's `filtered()` method against a list of scheduled/used IDs.

Example of problematic code:
```python
all_partners = self.env['res.partner'].search([])
planned_partner_ids = self.env['sale.visit.plan.line'].search(domain).mapped('partner_id.id')
# This loads thousands of partner records into memory to filter them
unscheduled_partner_ids = all_partners.filtered(lambda p: p.id not in planned_partner_ids).ids
```

If the database contains tens of thousands of records, this search will load all of them into the server's RAM. This causes high CPU usage, memory bloating, and can crash the worker process.

## Root Cause

Using `self.env['model'].search([])` returns a full recordset. Calling `.filtered(lambda r: ...)` on it forces Odoo to instantiate Python objects for every single record in the table. This bypasses the database's native indexing and querying capabilities.

## Solution ✅

Push the exclusion/filtering logic down to the database level using Odoo's SQL/ORM domain parameters (`not in` operator).

Instead of fetching and filtering in memory:
```python
planned_partner_ids = self.env['sale.visit.plan.line'].search(domain).mapped('partner_id.id')
# Directly pass the 'not in' condition to the action window domain
return {
    'name': 'Unscheduled Customers',
    'res_model': 'res.partner',
    'domain': [('id', 'not in', planned_partner_ids)],
    'view_mode': 'list,form',
    'type': 'ir.actions.act_window',
}
```

This ensures Odoo runs a single optimized SQL query:
```sql
SELECT id FROM res_partner WHERE id NOT IN (...);
```

## ⚠️ Pitfalls

- **Empty ID lists:** If the excluded IDs list (e.g., `planned_partner_ids`) is empty, `NOT IN (NULL)` or empty tuple behaves correctly in Odoo ORM (Odoo replaces it with `(1, '=', 1)`), but keep in mind that a huge list of excluded IDs (e.g., more than 10,000) might hit database query parameter limits or slow down the SQL `NOT IN` operation. If the list is extremely large, consider using a custom SQL subquery or joining tables.

## Verification

Run Python code check or profile the SQL queries using Odoo's query logger:
```python
# Confirm no full table search is executed on the target model
```
