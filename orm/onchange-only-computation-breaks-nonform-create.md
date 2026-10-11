# onchange-only field computation breaks non-form create paths (portal / API / scripted)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-14                                 |
| Author        | Gamal Mansour                              |

**Tags:** `orm`, `onchange`, `create`, `portal`, `controller`, `not-null`, `required`

---

## Problem

> A **required** field is auto-filled only by an `@api.onchange`. The backend
> form works fine (the onchange runs in the UI), but any create that does NOT go
> through that form — a portal controller doing `Model.create({...})`, an
> import, a scripted create — leaves the field empty and hits the DB constraint.

```
ERROR: null value in column "date_to" of relation "sale_visit_plan" violates not-null constraint
# portal controller returns HTTP 422; nothing is created
```

Real case: `sale.visit.plan.date_to` (`required=True`) was filled only by
`@api.onchange('date_from')`. Creating a plan from the backend form worked;
creating one from the portal "New Plan" controller (`sale.visit.plan.create({
'date_from': ...})`) always 422'd — the portal create feature was silently
broken because the onchange never ran.

## Root Cause

`@api.onchange` runs **only** in the web client form (a client→server round trip
on field edit). The ORM `create()` / `write()` do **not** trigger onchange
methods. So any business logic that lives *only* in an onchange is invisible to
every programmatic caller (controllers, `env[...].create`, XML-RPC, imports).

## Solution ✅

> Put the computation in a shared helper and call it from **both** the onchange
> and `create()` (fill only when missing, so form saves that already carry the
> value are untouched). A computed-stored field or a `default` are alternatives.

```python
@api.model
def _visit_plan_end_date(self, date_from, company=None):
    if not date_from:
        return False
    mode = (company or self.env.company).visit_plan_end_date_mode
    if mode == 'month':
        return date_from + relativedelta(months=1, days=-1)
    if mode == 'year':
        return date_from + relativedelta(years=1, days=-1)
    if mode == 'same_day':
        return date_from
    return date_from + relativedelta(days=6)   # 'week' (default)

@api.onchange('date_from')
def _onchange_date_from(self):
    for plan in self:
        if plan.date_from:
            plan.date_to = self._visit_plan_end_date(plan.date_from, plan.company_id)

@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('date_from') and not vals.get('date_to'):
            company = (self.env['res.company'].browse(vals['company_id'])
                       if vals.get('company_id') else self.env.company)
            vals['date_to'] = self._visit_plan_end_date(
                fields.Date.to_date(vals['date_from']), company)
    return super().create(vals_list)
```

## ⚠️ Pitfalls

- Don't patch only the calling controller — fix the **model** so every create
  path (portal, import, RPC, future callers) is correct in one place.
- Guard with `if not vals.get(field)` so backend form saves (which already send
  the onchange-filled value) are not overwritten.
- This bug is **invisible in the backend UI** — only non-form callers hit it. A
  green backend never proves the portal/API path works.

## Verification

> Add a test that creates through the non-form path (HTTP POST to the portal
> route, or a bare `env[...].create`), not just the form.

```python
# HttpCase: POST the portal create route and assert the record now exists
resp = self.url_open('/my/visit-plans/new', allow_redirects=False, data=payload)
self.assertEqual(self._plan_count(), before + 1)
```

## References

- Related file: `security/portal-controller-sudo-browse-bypasses-record-rules-idor.md`
- Related file: `views/portal-workflow-rule-viewer-bypass.md`
