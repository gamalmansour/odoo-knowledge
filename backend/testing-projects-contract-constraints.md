# Testing Projects with Contract Constraints

**Category:** Backend  
**Tags:** Testing, Constraints, Construction Project, Contract Owner  
**Last Verified:** 2026-06-15  
**Odoo Versions:** 17.0+  

## Context
When writing automated tests (`TransactionCase`) for any module that extends or depends on `construction_project`, you may encounter `NotNullViolation` errors when trying to create a mock `construction.project`.

## Problem ⚠️
The `construction_project` model has strict database-level dependencies on the `contract_owner` model and other date fields. Attempting to create a simple mock project like:
```python
self.env['construction.project'].create({'name': 'Test'})
```
Will trigger errors such as:
- `psycopg2.errors.NotNullViolation: null value in column "contract_id"`
- `psycopg2.errors.NotNullViolation: null value in column "date_signed"`
- `psycopg2.errors.NotNullViolation: null value in column "date_start"`
- `psycopg2.errors.NotNullViolation: null value in column "contract_value_original"`

## Solution ✅
You MUST explicitly mock a complete `contract.owner` record first, fulfilling all its required fields, and link it to the project, while also fulfilling the project's own required fields:

```python
# 1. Create a dummy client
client = self.env['res.partner'].create({'name': 'Test Client'})

# 2. Create a dummy contract fulfilling all NOT NULL constraints
contract = self.env['contract.owner'].create({
    'name': 'Test Contract',
    'owner_id': client.id,
    'date_signed': '2026-01-01',
    'date_start': '2026-01-01',
    'date_end_planned': '2026-12-31',
    'contract_value_original': 1000000.0,
})

# 3. Create the project linked to the contract
project = self.env['construction.project'].create({
    'name': 'Test Project',
    'code': 'TST', # Use code, not reference
    'contract_id': contract.id,
    'date_start': '2026-01-01',
    'date_end': '2026-12-31',
})
```

## Pitfalls to Avoid ⚠️
- Assuming `construction.project` uses standard Odoo fields. For instance, the project code is stored in `code`, not `reference`.
- Relying on ORM `required=True` defaults. Some fields have raw SQL `NOT NULL` constraints that will fail hard at the database level during test transaction flushes.
