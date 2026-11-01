# Changing Search Fields in Target Models

## Problem
When migrating a model (like `sale.target`) from using specific `month` and `year` fields to generic `date_from` and `date_to` fields, dependent models (like `commission_settlement`) that query targets based on `month` and `year` will break and throw programming errors.

## Solution ✅
Always search the codebase for references to the deprecated fields across all custom modules. Refactor dependent searches to use overlapping date domains `[('date_from', '<=', settlement.date_to), ('date_to', '>=', settlement.date_from)]`.

## ⚠️ Pitfalls
Forgetting to check `commission_settlement` or other dependent models, or forgetting portal controllers/views which might use the removed fields for ordering or display.

## Odoo Versions
All versions
