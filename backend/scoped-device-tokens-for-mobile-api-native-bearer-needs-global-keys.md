# Mobile-API device tokens: Odoo 19's native bearer auth only accepts GLOBAL api keys — build a scoped auth method instead

## Metadata
- **Category:** backend
- **Severity:** 🟡 Medium
- **Odoo Versions:** 19 (bearer method); apikeys mechanics 14+
- **Tags:** `auth`, `bearer`, `res.users.apikeys`, `mobile`, `rest-api`, `scope`, `mfa`, `session`, `security`
- **Last Verified:** 2026-08-12 (pure_mobile_api, Odoo 19)

## Problem 🔴

Building token auth for a mobile app on Odoo 19, the obvious move is
`auth='bearer'` on the routes. Three traps:

1. **`_auth_method_bearer` checks `scope='rpc'`** — and the core comment
   says it out loud: *"'rpc' scope does not really exist, we basically
   require a global key (scope NULL)"*. So the native method only accepts
   UNSCOPED keys — a leaked mobile token would be a full external-RPC
   credential for that user.
2. **`res.users.apikeys._generate(scope, name, expiration_date)`** raises
   `ValidationError` for non-system users without an expiration date, and
   caps the duration at `max(group.api_key_duration) or 1.0` **days** — a
   portal rep's token would silently die in a day. Called as
   `.sudo()._generate(...)` the cap disappears AND `user_id` stays the
   authenticated user (since v13 `sudo()` keeps `env.uid`, only flips
   `su`).
3. **MFA detection after `request.session.authenticate(env, credential)`**:
   the returned `auth_info['uid']` is set even when the account still needs
   the TOTP step (it is `pre_uid`). The reliable signal is
   `request.session.uid` — it stays `None` until `finalize()` runs.

## Solution ✅

1. Custom auth method with its own scope, mirroring the stateless part of
   the core bearer:

```python
class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _auth_method_pure_mobile(cls):
        token = <parse "Authorization: Bearer ...">
        uid = request.env['res.users.apikeys']._check_credentials(
            scope='pure_mobile', key=token)
        if not uid:
            raise werkzeug.exceptions.Unauthorized(...)
        request.update_env(user=uid)          # record rules apply normally
        request.session.can_save = False      # stateless
```

2. Mint per-device keys at login (after `session.authenticate` +
   `request.session.uid` check):

```python
token = request.env['res.users.apikeys'].sudo()._generate(
    'pure_mobile', f'Mobile — {device_name}',
    fields.Datetime.add(fields.Datetime.now(), days=180))
```

3. Map token→device WITHOUT storing the key: keep `token[:8]` (mirrors the
   core `INDEX_SIZE = 8`) on the device record and look up by
   `(user_id, key_index)`. Revocation = `apikey.unlink()` +
   `env.registry.clear_cache()` (the credential check is LRU-cached — skip
   the cache clear and revoked tokens keep working until restart).

## ⚠️ Pitfalls

- `type='json'` routes wrap everything in JSON-RPC envelopes — for clean
  REST use `type='http'` + `request.make_json_response(...)` + `csrf=False`
  (the token IS the credential).
- Don't trust the client's `Content-Type` for uploads — sniff magic bytes
  (JPEG `FF D8 FF`, PNG `89 50 4E 47`, WEBP `RIFF..WEBP`).
- Rate-limit the (necessarily public) login route yourself; nothing in core
  does it for you.

## Related
- `backend/controller-to-model-extraction-keep-unguarded-casts-inside-original-guards.md` (the service layer these routes call)
