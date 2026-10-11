# Stock quantities are env.companies-scoped even under sudo()

**Category:** ORM / Inventory / Multi-company
**Date:** 2026-07-22
**Project:** activity (store API — "backend shows 10, API shows 0" on the client's test server)

## Symptom
Admin backend shows On Hand = 10 (quant in a second company's warehouse, reserved 0). A public API endpoint reading the SAME variant via `sudo()` returns `free_qty = 0`. No error anywhere.

## Root cause (core source, addons/stock/models/product.py `_get_domain_locations`)
```python
location_ids = set(Warehouse.search(
    [('company_id', 'in', self.env.companies.ids)]   # explicit domain!
).mapped('view_location_id').ids)
```
Quantity computes (`qty_available`/`free_qty`/`virtual_available`) restrict to warehouses of **`env.companies`** via an EXPLICIT search domain — **not** a record rule, so `sudo()` does NOT widen it. A public/http user carries only the main company → quants in any other company's warehouse silently read as 0.

## Fix
Read quantities `with_company(<the company that will actually sell to this caller>)` — in the activity platform that's `_company_for_country(caller.activity_country_id)`, the same company the cart bills (availability then always matches what checkout can fulfil):
```python
products = products.with_company(_company(_caller()))
```

## Data prerequisites on the server (or the mapping falls back to the main company)
1. The selling company's **Country** field must be set (the fixed `_company_for_country` matches on `partner_id.country_id`).
2. The app user's `activity_country_id` must be set.

## Rule of thumb
`sudo()` bypasses ACLs and record rules — it does NOT bypass explicit company-scoping domains built from `env.companies` (stock quantities being the classic case). When a sudo read shows less than the backend, check `env.companies`, not permissions.
