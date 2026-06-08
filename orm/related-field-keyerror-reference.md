# KeyError: Field referenced in related field definition does not exist

## Metadata
- **Category:** ORM
- **Severity:** 🔴 Critical
- **Odoo Versions:** All
- **Tags:** `orm`, `related`, `fields`, `keyerror`, `registry`
- **Last Verified:** 2026-06-08
- **Author:** ENG/Gamal Mansour

## Problem ❌
During module installation or upgrade, the server fails to load the registry and raises a `KeyError` indicating that a field used in a `related` field definition doesn't exist:
```text
KeyError: 'Field client_id referenced in related field definition construction.project.client_id does not exist.'
```

## Root Cause 🔍
This happens when you define a `related` field that traverses through another model (e.g., `related='contract_id.client_id'`), but the target field (`client_id`) does **not exist** on the intermediate model (`contract.owner`). 
This typically occurs due to:
1. Typos in the target field name (e.g., typing `client_id` instead of `owner_id`).
2. The field exists in a different module that has not been added to the `depends` list in `__manifest__.py`.
3. Trying to access a field that was removed in a newer Odoo version.

## Solution ✅
1. Double-check the exact field name on the intermediate model (e.g., check `contract.owner` to ensure it has `owner_id`, not `client_id`).
2. Ensure the module where the target field is defined is listed in `depends`.
3. Fix the related path:
**Before:**
```python
client_id = fields.Many2one(related='contract_id.client_id') # Typo or missing field
```
**After:**
```python
client_id = fields.Many2one(related='contract_id.owner_id') # Correct field name
```

## ⚠️ Pitfalls
- **Accidentally overriding instead of extending:** If you intended to add the field to the intermediate model via inheritance, make sure the `_inherit` file is imported in your `models/__init__.py` and the module depends on the parent module. If the field is not loaded before the related field is evaluated, the `KeyError` will persist.
