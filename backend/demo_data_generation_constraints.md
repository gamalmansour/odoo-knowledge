# Demo Data Generation Constraints

**Category:** Backend  
**Tags:** Demo Data, Constraints, ValueErrors, Idempotent Generation  
**Odoo Versions:** V17  
**Last Verified:** 2026-06-16

## Problem
When writing automated python scripts to generate demo data or seeding a database across many interconnected custom modules (like `construction_claims_eot`, `construction_dlp`, `construction_hse`), `ValueError` exceptions are frequently raised when passing fields that do not exactly match the destination `_name` model schema.
Common issues encountered:
- Supplying `.create()` with fields like `date_practical_completion` when the actual field is `practical_completion_date`.
- Providing `priority` instead of `severity`.
- Overlooking required database fields leading to `psycopg2.errors.NotNullViolation`.
- Using `state` when the specific module uses `status`.

## Solution ✅
1. Always grep the exact model definition `_name = 'my.model'` before creating demo dictionaries to ensure required fields and choices map perfectly.
2. If `psycopg2.errors.NotNullViolation` occurs on a field that wasn't included in your dict, it means the field has `required=True` at the ORM level (or database level) but wasn't populated.
3. Use a centralized dictionary mapping or explicitly check `views` / `models` for the valid `Selection` keys (like `draft, assigned, fixed` vs `open, in_progress, rectified`).
4. Ensure idempotency by fetching an external ID using `env['ir.model.data']._update` or using a `_get_or_create` logic for your demo generator to avoid duplicate constraints breaking on consecutive runs.

## ⚠️ Pitfalls
- Random choices `random.choice(['state1', 'state2'])` will fail hard if the exact string isn't in the model's `Selection` array.
- Avoid guessing date fields (e.g., `date_reported` instead of `reported_date` or `date_start` instead of `start_date`); they differ between module domains.
