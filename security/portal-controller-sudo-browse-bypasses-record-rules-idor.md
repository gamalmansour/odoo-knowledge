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

### Centralize it (Option A, done once)

Instead of editing 21 sites by hand, route them all through one helper that
reads via the user's own rights (so the rule decides) and hands back a `sudo`
recordset for the privileged writes the routes already do:

```python
def _get_portal_visit(self, visit_id):
    # search() applies ir.rules; a record the rule filters out → empty set.
    visit = request.env['sale.visit'].search([('id', '=', visit_id)])
    return visit.sudo()   # privileged writes downstream keep working
```

```python
visit = self._get_portal_visit(visit_id)
if not visit:
    return request.redirect('/my/visits')
```

> ⚠️ **The rule must cover every *legitimate* access path before you switch to Option A.**
> Here the app granted supervisors access two ways — the salesperson is their
> subordinate **and** they own the visit's plan — but `rule_sale_visit_portal`
> only encoded the first. Relying on the rule without adding
> `('plan_line_id.plan_id.supervisor_id', '=', user.id)` would have silently
> revoked plan-based access. Read the controller's *intended* access (its list
> domains, its counters) and make the rule match it, then delete the manual check.

### Two flavors of the same bug to grep for

1. **Weak check:** `salesperson_id == user OR _is_supervisor_user(user)` — supervisor over-reach.
2. **No record check at all:** routes that only gate `if not _is_supervisor_user(user): redirect` and then `sudo().browse(id)` — *any* supervisor mutates *any* record (here: approve-end, mark successful/unsuccessful, write supervisor notes). This is strictly worse and easy to miss because it "looks" gated.

### Don't forget child / sub-objects

A route can authorize the parent correctly and still IDOR a child. Example:
reorder approve/reject verified `plan.supervisor_id == user` but then
`browse(ro_id).action_approve()` without checking the reorder belonged to that
plan — so a supervisor approves reorders on *other* plans via their own plan id
in the URL. Always tie the sub-object back to the authorized parent:
`reorder.plan_line_id.plan_id == plan`.

## ⚠️ Pitfalls

- A `sudo()` on the `browse` is invisible in single-user/admin testing — admin passes every check, so the hole only shows with a real low-privilege portal account.
- Role-membership checks (`user in group`) are **not** record-level authorization. "Is a supervisor" ≠ "supervises THIS record".
- Don't forget multi-company: even Option B leaks across companies unless the model also has a multi-company `ir.rule`.
- `browse()` of a rule-filtered id returns an empty recordset on access, so test with `.exists()` rather than catching exceptions. For Option A prefer `search([('id','=',id)])`, which **applies the rules** and returns empty cleanly — plain `browse().exists()` does **not** re-apply record rules.
- Adding the multi-company `ir.rule` only helps the routes that actually drop `sudo()`. A route that keeps `sudo()` bypasses the company rule too — Option A (read as the user) is what makes the company rule bite.
- Child line models often have **no `company_id`** of their own. Scope their multi-company rule through the parent: `[('visit_id.company_id','in',company_ids)]`, else they stay cross-company readable even after the parent is locked down.
- A `search`-based fetch needs the portal group to hold a model-level **read ACL** (`ir.model.access.csv`); without it you get `AccessError` instead of an empty set. Verify the ACL exists before switching off `sudo`.

## Test it

A `post_install` `HttpCase` is the cheapest proof. Authenticate as a low-priv
portal user (and, critically, as a *supervisor who supervises nobody relevant*)
and assert `GET /my/visits/<foreign-id>` returns a 3xx to the list, while the
owner gets 200. Back it with an ORM-layer check that
`Visit.with_user(attacker).search([('id','=',id)])` is empty.

## Verification

```bash
# Find every sudo-browse-then-manual-check in controllers
grep -rn "\.sudo()\.browse(" custom/<module>/controllers/
# Then log in as a low-privilege portal user and try /my/<route>/<id> for an id you don't own.
```

## References

- Related file: `security/dynamic-portal-section-visibility.md`
- Related file: `orm/bypass-record-rules-duplicate-validation.md`
