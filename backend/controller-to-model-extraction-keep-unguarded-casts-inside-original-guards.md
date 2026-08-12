# Controller→Model extraction: unguarded casts must stay inside their original guards or silent 302s become 500s

## Metadata
- **Category:** backend
- **Severity:** 🟡 Medium
- **Odoo Versions:** All
- **Tags:** `refactoring`, `controllers`, `portal`, `service-layer`, `parity`, `int-cast`, `state-guard`, `rest-api`
- **Last Verified:** 2026-08-12 (Odoo 19, sale_visit Phase 0 extraction — pure_mobile project)

## Problem 🔴

When extracting business logic from portal controllers into model "service"
methods (e.g. to share ONE implementation between a website portal and a
mobile JSON API), the natural split is: controller keeps HTTP parsing, model
gets the state guards + writes.

That split silently changes behavior for malformed input: the original code
parsed form values INSIDE its guards (`if visit.state == 'in_progress':`
before `int(kw.get('product_id') or 0)`), so garbage input against a
non-writable record answered with the route's silent redirect. After moving
the guard into the model, the controller parses FIRST — and every unguarded
`int()`/`float()` cast that used to be unreachable now raises → HTTP 500
where the portal used to answer 302.

In a 38-route extraction (sale_visit), an adversarial line-by-line review
found exactly 4 of these — all the same pattern, none caught by syntax
checks or happy-path tests:
- `add-shortage` (unguarded `int(product_id)` behind an in_progress guard)
- `update-delivered-products` (unguarded `int(reason_id)` behind in_progress)
- plan `add-line` (unguarded int casts behind a draft-plan guard)
- plan `update-line` (casts behind draft-plan AND valid-line checks)

## Solution ✅

1. In the controller, keep (or re-duplicate) the ORIGINAL guard around the
   parse block, even though the model method re-checks it — the duplicated
   check is cheap, and the model's own guard stays as the API-safety net:

```python
if visit.state == 'in_progress':          # parity guard around the parse
    product_id = int(kw.get('product_id') or 0)   # original unguarded cast
    visit.portal_add_shortage(product_id, qty, notes)
return request.redirect(...)
```

2. Verify a parity-critical refactor with an **adversarial diff review**
   whose brief is "refute byte-identical", tracing per route: guard ORDER,
   which casts are guarded vs unguarded, joint-vs-independent `try` blocks
   (`lat/lng` parsed in ONE try → either bad collapses BOTH to None),
   positional index semantics of parallel `*[]` arrays (an invalid entry
   still consumes its `(i+1)*10` sequence slot), and `sudo()` placement
   (search-as-user THEN sudo is an anti-IDOR idiom, not redundancy).

## ⚠️ Pitfalls

- "Wrap every cast in try/except" is NOT parity — casts that 500 today for
  in-guard states must KEEP 500ing, or you've changed observable behavior
  the other direction.
- `float(x or 0) or None` collapses BOTH parse failures and legitimate 0.0
  to None — preserve the idiom, don't "clean it up" mid-refactor.
- Moving a log line into the model changes the logger name (usually fine)
  but `self.env.user` under `sudo()` still renders the acting user in
  Odoo ≥ 13 — uid is preserved, only `su` flips.

## Related
- `misc/running-module-tests-demo-and-port-collisions.md` (testing the result)
