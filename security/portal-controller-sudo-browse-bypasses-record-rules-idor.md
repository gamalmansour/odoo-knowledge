# Portal Controller `sudo().browse()` Bypasses Record Rules → IDOR

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `portal`, `controller`, `sudo`, `ir.rule`, `idor`, `record-rules`

---

## Problem

> A portal/website controller fetches a record with `.sudo().browse(record_id)` and then authorizes the request with a hand-written ownership check. The manual check is weaker than the `ir.rule` it replaced, so an authenticated user can read or modify records that don't belong to them by enumerating IDs in the URL (e.g. `/my/visits/1..N`). Classic Insecure Direct Object Reference (IDOR).

```python
# controllers/portal.py  — VULNERABLE
visit = request.env['sale.visit'].sudo().browse(visit_id)
if visit.salesperson_id.id != user.id and not self._is_supervisor_user(user):
    return request.redirect('/my')
# _is_supervisor_user only checks the user IS a supervisor — never that THIS
# record belongs to one of their subordinates. A correct ir.rule existed, but
# .sudo() discarded it. Any supervisor account now reaches EVERY record, cross-company.
```

## Root Cause

`.sudo()` runs as superuser and **switches off all `ir.rule` record rules** for that recordset. The carefully-written portal rule (own + subordinate records, company-scoped) never runs. The manual `if` that replaces it almost always covers fewer cases than the rule — here it grants every "supervisor" access to every record instead of only their subordinates'.

## Solution ✅

> Prefer letting the record rules do the work. Only keep `sudo()` if you genuinely need to read a field the user can't, and then re-impose the ownership predicate yourself.

```python
# Option A (best): no sudo — the ir.rule enforces visibility.
visit = request.env['sale.visit'].browse(visit_id)
if not visit.exists():
    return request.redirect('/my')   # rule filtered it out → 404-style redirect

# Option B: keep sudo but re-impose the FULL ownership predicate.
visit = request.env['sale.visit'].sudo().browse(visit_id)
user = request.env.user
owns = visit.salesperson_id == user
supervises = self._is_supervisor_user(user) and (
    visit.salesperson_id in user.subordinate_ids
    or visit.plan_line_id.plan_id.supervisor_id == user
)
if not (owns or supervises):
    return request.redirect('/my')
```

Audit **every** place a "is this user a manager/supervisor" helper is used as an authorization gate — the bug repeats across every route that copy-pasted the pattern (here ~21 routes).

## ⚠️ Pitfalls

- A `sudo()` on the `browse` is invisible in single-user/admin testing — admin passes every check, so the hole only shows with a real low-privilege portal account.
- Role-membership checks (`user in group`) are **not** record-level authorization. "Is a supervisor" ≠ "supervises THIS record".
- Don't forget multi-company: even Option B leaks across companies unless the model also has a multi-company `ir.rule`.
- `browse()` of a rule-filtered id returns an empty recordset on access, so test with `.exists()` rather than catching exceptions.

## Verification

```bash
# Find every sudo-browse-then-manual-check in controllers
grep -rn "\.sudo()\.browse(" custom/<module>/controllers/
# Then log in as a low-privilege portal user and try /my/<route>/<id> for an id you don't own.
```

## References

- Related file: `security/dynamic-portal-section-visibility.md`
- Related file: `orm/bypass-record-rules-duplicate-validation.md`
