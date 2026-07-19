# HttpCase Has No PUT/DELETE Helper, and Date-Field Conversion Raises Bare ValueError

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `testing`, `httpcase`, `url_open`, `requests-session`, `fields.Date`, `ValueError`, `savepoint`, `rest-api`, `400-vs-500`

---

## Problem

Two separate traps hit together when adding idiomatic `PUT`/`DELETE` REST endpoints (e.g. "edit my profile", "archive my child") and their `HttpCase` tests:

1. `HttpCase.url_open(url, data=..., headers=...)` only ever issues `GET` or `POST` — there is no `method=` kwarg. A test written as `self.url_open(path, data=json.dumps(payload), headers={...})` for a `PUT`/`DELETE` route silently sends a `POST`, and the route (registered with `methods=['PUT']`) 404s or 405s, not what the test author expects.
2. A route handler that does `child.write({'activity_birth_date': data['birth_date']})` with a malformed date string (e.g. `"not-a-date"`) does **not** raise `odoo.exceptions.ValidationError` — it raises a bare `ValueError` from `fields.Date.to_date` → `datetime.strptime(value, DATE_FORMAT)`. A handler that only catches `except (UserError, ValidationError)` around the `write()` lets that `ValueError` propagate to a `500`, even though the endpoint's contract promises `400` for bad input.

## Root Cause

1. `odoo/tests/common.py`'s `HttpCase.url_open` (`def url_open(self, url, data=None, files=None, timeout=12, headers=None, allow_redirects=True, head=False)`) branches only on `data`/`files` truthiness to choose `.post()` vs `.get()` on `self.opener`. There is no verb parameter.
   `self.opener` is `Opener(requests.Session)` (`class Opener(requests.Session)`, same file) — a full `requests.Session` subclass that flushes/clears the test cursor on every `.request()` call, so **any** `requests.Session` method works, including ones `url_open` doesn't wrap.
2. `odoo/fields.py`'s `Date.to_date` is a thin `datetime.strptime(value[:DATE_LENGTH], DATE_FORMAT)` — no try/except, no `ValidationError` wrapping. `Date.convert_to_cache` calls it directly during `write()`/`create()`. Only `ir.model` field-level constraints (`@api.constrains`) raise `ValidationError`; raw type conversion failures do not.

## Solution ✅

```python
# 1) PUT/DELETE in HttpCase tests: bypass url_open, call self.opener directly.
def _put(self, path, payload, token=None):
    headers = {'Content-Type': 'application/json',
               'Authorization': 'Bearer %s' % (token or self.token)}
    return self.opener.put(self.base_url() + path, data=json.dumps(payload),
                           headers=headers, timeout=30)

def _delete(self, path, token=None):
    headers = {'Authorization': 'Bearer %s' % (token or self.token)}
    return self.opener.delete(self.base_url() + path, headers=headers, timeout=30)
```

```python
# 2) Controller: widen the except clause AND wrap in a savepoint, so a bad
#    cast degrades to 400 instead of a 500 that also poisons the transaction.
try:
    with request.env.cr.savepoint():
        if vals:
            partner.write(vals)
except (UserError, ValidationError, ValueError, TypeError) as err:
    return api_utils.json_error('bad_request', str(err), status=400)
```

For a `Many2one` id coming from client JSON, validate existence explicitly *before*
`write()` rather than relying on exception handling — a non-existent FK id trips a DB
`IntegrityError` (not `ValueError`), which the widened `except` above still won't catch:

```python
if not request.env['res.country'].sudo().browse(country_id).exists():
    return api_utils.json_error('bad_request', _('Unknown country id.'), status=400)
```

## ⚠️ Pitfalls

- Don't "fix" this by adding a `method` parameter to a shared `_req()` helper that still
  calls `url_open` — `url_open` has no verb switch to plumb it into. Route straight to
  `self.opener.<verb>()` for anything beyond GET/POST.
- The same bare-`ValueError` gap applies to any `fields.Date`/`fields.Datetime` write from
  untrusted input, not just this endpoint — audit every controller that writes a date/datetime
  field from request JSON without a savepoint + wide except.
- `Integer`/`Many2one` id fields silently coerce most garbage via `int(value or 0)` — but an
  id that parses fine and simply doesn't exist (or belongs to the wrong model) still needs an
  explicit `.exists()` check; it won't raise until the FK constraint fires at flush/commit time,
  by which point you're in `IntegrityError` territory, not `ValueError`.

## Verification

```bash
# HttpCase test asserting 400, not 500, on a malformed date:
def test_update_profile_bad_birth_date_400(self):
    res = self._put('/api/v1/profile', {'activity_birth_date': 'not-a-date'})
    self.assertEqual(res.status_code, 400)
    self.assertFalse(self.parent.activity_birth_date)  # write rolled back via savepoint
```

## References

- Related file: `misc/running-module-tests-demo-and-port-collisions.md` (HttpCase port/demo setup)
- Related file: `security/portal-controller-sudo-browse-bypasses-record-rules-idor.md` (the
  ownership-recheck-after-sudo() pattern used alongside this in the same controllers)
