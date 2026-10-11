# `self.assertRaises` rolls back side-effects written before the `raise`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend (testing)                          |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `testing`, `assertRaises`, `savepoint`, `rollback`, `UserError`, `side-effects`

---

## Problem

A method deliberately writes to the DB **before** raising (an attempt counter, a
revocation flag, an audit row) — a very common "charge the attempt, then reject"
pattern:

```python
otp.attempts += 1                     # persist the failed attempt...
if not self._hash_equal(code, otp.code_hash):
    raise UserError(_('Invalid or expired code.'))   # ...then reject
```

The production behaviour is correct, but the test that asserts the side-effect
**fails**:

```python
with self.assertRaises(UserError):
    self.Otp._verify(phone, 'wrong')
otp = self.Otp.search([('phone', '=', phone)], limit=1)
self.assertEqual(otp.attempts, 1)     # AssertionError: 0 != 1
```

Same symptom bit a "reuse of a rotated refresh token revokes the whole family"
check: after the reuse call the family was still live, because the revoking
`write` happened right before the `raise`.

## Root Cause

Odoo's `BaseCase.assertRaises` (see `odoo/tests/common.py`) wraps the block in a
**savepoint** and rolls it back when the exception fires — so the transaction
stays usable after an expected `IntegrityError`/`UserError`. That rollback also
discards every ORM write the method performed *before* it raised. The assertion
then reads the pre-write value.

This is **not** a bug in the code under test — outside `assertRaises` (real
request, or a plain `try/except`) the writes commit normally.

## Solution ✅

When you need to assert a side-effect that happened *before* the raise, catch the
exception yourself with `try/except` (no savepoint) instead of `assertRaises`:

```python
def _verify_expecting_failure(self, phone, code):
    try:
        self.Otp._verify(phone, code)
        self.fail('Expected UserError was not raised.')
    except UserError:
        pass

def test_wrong_code_counts_attempt(self):
    self.Otp._issue(phone, 'login', partner=self.parent)
    self._verify_expecting_failure(phone, 'wrong')
    self.assertEqual(self.Otp.search([('phone', '=', phone)]).attempts, 1)  # now 1 ✅
```

Keep plain `assertRaises` when you only care **that** it raised and not about any
partial write it left behind (e.g. asserting a duplicate-key `IntegrityError`).

## ⚠️ Pitfalls

- Don't "fix" it by moving the counter write *after* the raise — that changes
  real behaviour (the attempt would no longer be charged on failure). The test
  is wrong, not the code.
- A bare `except Exception: pass` can swallow a real bug; catch the specific
  exception and call `self.fail(...)` on the no-raise path so a silent success
  still fails the test.
- The mirror image also holds: a test that *relies* on `assertRaises` rolling
  back (to keep the cursor clean after an `IntegrityError`) must keep using it —
  a `try/except` around a DB-level error leaves the cursor aborted.

## Verification

```bash
.venv/bin/python odoo-bin -c odoo17_dev.conf -d <db> -u activity_auth \
  --test-enable --test-tags /activity_auth --stop-after-init \
  --http-port 8911 --gevent-port 8912 --max-cron-threads=0
# => odoo.tests.result: 0 failed, 0 error(s)
```

## References

- Related file: `orm/idempotent-create-unique-constraint-savepoint.md` (savepoint
  flush-on-exit semantics for the *opposite* case — containing an IntegrityError)
- Code: `activity/activity_auth/tests/test_auth_models.py`
