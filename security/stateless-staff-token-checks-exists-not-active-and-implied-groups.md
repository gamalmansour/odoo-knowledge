# A Stateless Staff Token Outlives Offboarding: `exists()` Is Not `active`, and Groups Imply Each Other

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                    |
| Odoo Versions | All                                         |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-08-19                                  |
| Author        | ENG/Gamal Mansour                           |

**Tags:** `security`, `jwt`, `rest-api`, `res.users`, `active`, `exists`, `has_group`, `implied_ids`, `offboarding`, `rate-limit`

---

## Problem

A REST API authenticates staff with a stateless bearer token (JWT, 8h TTL) and
re-checks authorization on every request — which looks completely sound:

```python
uid = int(claims['sub'])
user = request.env['res.users'].sudo().browse(uid).exists()
if not user or not _staff_role(user):
    return json_error('forbidden', 'Not an active staff account.', status=403)
request.update_env(user=uid)
request.activity_staff_role = claims.get('role')     # <-- from the TOKEN
```

Three defects, none of which raises anything:

1. **Archiving a user does not revoke access.** `.exists()` asks "is the ROW
   there", not "is the account enabled". `has_group()` answers happily for an
   archived user. So an offboarded admin keeps full API access until their token
   expires — up to the whole TTL, and the token cannot be revoked because it is
   stateless. Archiving is usually the *only* lever an operator has.
2. **The role is read back from the token**, so a user demoted from
   `super_admin` to `coach` still presents `role='super_admin'` for the rest of
   the TTL. Harmless until the first endpoint gates on it — then it is a silent
   privilege-escalation window.
3. **The login route had no rate limit.** Odoo ships no brute-force lockout of
   its own (neither the web form nor `res.users.authenticate`), so a
   `cors='*'`, `csrf=False` JSON login endpoint is an open password oracle for
   real accounts, the superuser included.

## Root Cause

`exists()` maps to `SELECT id FROM res_users WHERE id IN %s` — no `active`
predicate, by design (it is a row-existence probe, not an ACL). The usual safety
net does not apply either: `active_test` filtering happens in `search()`, and
this code path never searches.

And claims are a **snapshot at mint time**. Any authorization fact copied into a
token is frozen for the token's lifetime; only facts re-read from the database
per request reflect the present.

## Solution ✅

**1. Check `active` explicitly, and re-derive the role from current groups.**

```python
user = request.env['res.users'].sudo().browse(uid).exists()
if not user or not user.active or not _staff_role(user):
    return json_error('forbidden', _('Not an active staff account.'), status=403)

request.update_env(user=uid)
request.activity_staff_role = _staff_role(user)      # NOT claims.get('role')
```

**2. Throttle the credential route with two independent windows.**

```python
def _login_rate_ok(login):
    Rate = request.env['activity.rate.limit'].sudo()
    window = 900
    per_login = Rate._hit(f'adminlogin:{login.lower()}', 5, window)   # one account, many IPs
    per_ip    = Rate._hit(f'adminloginip:{_client_ip()}', 30, window) # one IP, many accounts
    return per_login and per_ip
```

Charge the window **before** the password check, or a correct guess sails
through a window that should already be closed.

## ⚠️ Pitfalls

- **Implied groups are materialised into `groups_id`.** A role ladder
  (`super_admin` ⇒ `admin` ⇒ `coach`) means creating a user with `admin` also
  writes `coach` into `groups_id`. So `user.groups_id -= admin` does **not**
  make them a non-staff user — they drop one rung. Any test asserting "removing
  the group revokes access" must strip the whole ladder; and any "highest role
  wins" helper must be ordered top-down, which is also why re-deriving the role
  works correctly after a demotion.
- `browse(uid).exists()` and `search([('id','=',uid)])` are **not**
  interchangeable here: the second one silently applies `active_test` and would
  have been correct by accident.
- Deactivating a user does not invalidate their `res.users.apikeys` or existing
  sessions either — the same reasoning applies to every stateless credential.
- Rate-limit counters written in the request transaction are lost if the request
  later rolls back. Return an error *response* from the route (as these
  controllers do) rather than raising, or the throttle silently un-counts every
  attempt it was meant to charge.
- Don't lengthen the TTL to "reduce logins". A stateless token's TTL **is** the
  revocation delay.

## Verification

```python
def test_archiving_revokes_a_live_token_immediately(self):
    token = self._login_and_get_token()
    self.assertEqual(self._me(token).status_code, 200)
    self.staff.active = False
    self.env.flush_all()
    self.assertEqual(self._me(token).status_code, 403)

def test_password_guessing_is_capped(self):
    for i in range(5):
        self.assertEqual(self._login('wrong-%s' % i).status_code, 401)
    self.assertEqual(self._login('wrong-again').status_code, 429)
    # And the cap must hold even for the RIGHT password:
    self.assertEqual(self._login('the-real-one').status_code, 429)
```

## References

- Related file: `backend/scoped-device-tokens-for-mobile-api-native-bearer-needs-global-keys.md`
- Related file: `security/portal-controller-sudo-browse-bypasses-record-rules-idor.md`
- Related file: `security/consolidating-duplicate-groups-xmlid-rename-and-link-vs-replace.md`
