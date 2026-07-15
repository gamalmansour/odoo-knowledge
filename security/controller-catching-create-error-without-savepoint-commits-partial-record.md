# A controller that catches a create()/write() error and returns a response — without a savepoint — COMMITS the partial record

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security (data-integrity)                  |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-15                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `controller`, `create`, `savepoint`, `rollback`, `constrains`, `data-integrity`, `api`

---

## Problem

An HTTP/API controller creates a record, catches the validation error, and
returns a clean `400` — but the **rejected record still gets saved**:

```python
# controllers/auth_controller.py — LEAKS a partial record
try:
    partner = Partner.create({'name': name, 'activity_phone': phone, ...})
    ...
except (UserError, ValidationError) as err:
    return json_error('bad_request', str(err), status=400)   # returns 400...
# ...but Odoo commits the request transaction on this normal return,
# and the INSERT that create() already issued is part of it.
```

Reported symptom: a user POSTed a register with an invalid phone (`{+966...}`),
got back `{"error": …}` in the client — then refreshed Odoo and found the
"failed" contact sitting in Contacts. Every rejected attempt had leaked a row.

## Root Cause

`create()` issues the INSERT, then the Python `@api.constrains` runs (on create /
at flush) and raises `ValidationError`. Catching that exception and **returning
normally** means the exception never reaches Odoo's request dispatcher — so the
dispatcher treats the request as successful and **commits** the transaction,
including the already-issued INSERT. The rollback that *would* have happened if
the exception propagated never occurs.

(A raw SQL/unique failure is even worse: it raises `psycopg2.IntegrityError`,
which poisons the cursor — without a savepoint the whole request 500s.)

## Solution ✅

Wrap every mutating block that you `try/except` around in a **savepoint**, so a
failure rolls back the partial write and only *then* is caught:

```python
try:
    with request.env.cr.savepoint():        # <-- the fix
        partner = Partner.create({...})
        code = Otp._issue(phone, purpose, partner=partner)
        SmsProvider._send_otp(phone, code)
except (UserError, ValidationError) as err:
    return json_error('bad_request', str(err), status=400)
except psycopg2.IntegrityError:             # for unique/SQL constraints
    return json_error('conflict', 'Already exists.', status=409)
```

`request.env.cr.savepoint()` flushes on enter/exit; on any exception inside the
`with` it rolls back to the savepoint and re-raises, so your `except` returns the
error while the DB is left clean.

## ⚠️ Pitfalls

- The bug is **invisible in the happy path and in most tests** — you only see it
  when a create is *rejected* and you then inspect the DB. Add a test that asserts
  the rejected request left **no** row (`search_count` unchanged).
- It applies to **every** create/write-then-catch in a controller, not just one
  route — grep the whole controllers dir. Here it affected register, add-child,
  create-subscription, and consent.
- `ValidationError` is a subclass of `UserError`, so `except UserError` catches
  both — but catching is exactly what hides the leak without the savepoint.
- Returning the error is correct UX; the missing piece is undoing the write.

## Verification

```python
def test_failed_register_persists_nothing(self):
    before = self.env['res.partner'].search_count([])
    r = self._post('/api/v1/auth/register', {'phone': '{+966513345678}', 'name': 'Junk'})
    self.assertEqual(r.status_code, 400)
    self.assertEqual(self.env['res.partner'].search_count([]), before)   # no leak
```

## References

- Related file: `orm/idempotent-create-unique-constraint-savepoint.md` (savepoint
  mechanics + the flush-on-exit detail)
- Code: `activity/activity_auth/controllers/auth_controller.py` (register)
