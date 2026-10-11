# Demo Data Generation Constraints

**Category:** Backend  
**Tags:** Demo Data, Constraints, ValueErrors, Idempotent Generation, Construction  
**Odoo Versions:** V17, V18  
**Last Verified:** 2026-10-02

## Problem
When writing automated python scripts to generate demo data or seeding a database across many interconnected custom modules (like `construction_claims_eot`, `construction_dlp`, `construction_hse`, `construction_dcc`, `construction_project`), `ValueError` exceptions are frequently raised when passing fields that do not exactly match the destination `_name` model schema.
Common issues encountered:
- Supplying `.create()` with fields like `date_practical_completion` when the actual field is `practical_completion_date`.
- Providing `priority` instead of `severity`.
- Overlooking required database fields leading to `psycopg2.errors.NotNullViolation`.
- Using `state` when the specific module uses `status` (or passing non-existent selection options like `in_progress` to `construction.meeting.action.status` which only accepts `open, done, cancel`).
- Providing lowercase discipline codes (`'civil'`, `'architectural'`) when `dcc_codes.py` defines uppercase selection keys (`'CIV'`, `'ARCH'`, `'STR'`, `'MEC'`, `'ELE'`).
- Passing input data for computed/non-stored fields (`actual_amount`, `committed_amount` in `construction.costcode.budget`) instead of `planned_amount`.

## Solution ✅
1. Always grep the exact model definition `_name = 'my.model'` before creating demo dictionaries to ensure required fields and choices map perfectly.
2. If `psycopg2.errors.NotNullViolation` occurs on a field that wasn't included in your dict, it means the field has `required=True` at the ORM level (or database level) but wasn't populated.
3. For relational dependencies, ensure master contracts (`contract.owner`) are created and committed before child projects (`construction.project`), since `construction.project.contract_id` is often strictly required.
4. For DCC models (`dcc.rfi`, `dcc.submittal`), use uppercase discipline codes from `DISCIPLINE_SELECTION` (`CIV`, `ARCH`, `STR`, `MEC`, `ELE`).
5. Use a centralized dictionary mapping or explicitly check `views` / `models` for the valid `Selection` keys (like `draft, assigned, fixed` vs `open, in_progress, rectified`).
6. Ensure idempotency by fetching an external ID using `env['ir.model.data']._update` or using a `_get_or_create` logic for your demo generator to avoid duplicate constraints breaking on consecutive runs.

## ⚠️ Pitfalls
- Random choices `random.choice(['state1', 'state2'])` will fail hard if the exact string isn't in the model's `Selection` array.
- Avoid guessing date fields (e.g., `date_reported` instead of `reported_date` or `date_start` instead of `start_date`); they differ between module domains.
- Attaching project photos: `construction.project` does not take raw image fields directly; use `construction.site.photo` records with `res_model='construction.project'` and `res_id=prj.id`.
