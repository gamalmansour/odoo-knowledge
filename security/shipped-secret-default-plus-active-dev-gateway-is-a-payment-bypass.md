# A Shipped Secret Default + an Active Dev Gateway = Full Payment Bypass

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                    |
| Odoo Versions | All                                         |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-08-19                                  |
| Author        | ENG/Gamal Mansour                           |

**Tags:** `security`, `payment`, `webhook`, `hmac`, `ir.config_parameter`, `post_init_hook`, `data-file`, `rest-api`, `money`

---

## Problem

A headless payment module ships two "harmless dev conveniences" in its data files:

```xml
<!-- data/ir_config_parameter.xml -->
<record id="param_webhook_secret" model="ir.config_parameter">
    <field name="key">activity.webhook_secret</field>
    <field name="value">dev-webhook-secret</field>   <!-- in source control -->
</record>

<!-- data/gateway_data.xml -->
<record id="gateway_stub" model="activity.payment.gateway">
    <field name="provider_type">stub</field>
    <field name="active" eval="True"/>               <!-- live on every install -->
</record>
```

and the model falls back to the same literal:

```python
def _webhook_secret(self):
    return self.env['ir.config_parameter'].sudo().get_param(
        'activity.webhook_secret', 'dev-webhook-secret')   # <-- known constant
```

Any app user can now mark **their own invoice paid without paying**:

1. `POST /api/v1/payments` — the response itself returns `provider_reference`.
2. Compute `X-Webhook-Signature = HMAC-SHA256('dev-webhook-secret', body)`.
   The key is in the public repo.
3. `POST /api/v1/payments/webhook/stub` with `{"provider_reference": "...", "status": "success"}`.
4. Signature verifies → `_handle_webhook` → `_register_payment()` → **invoice paid, zero money received.**

The same forged call confirms a `sale.order` and posts a real tax invoice on the store flow.

Nothing raises, nothing logs an anomaly, and the transaction looks perfectly legitimate in the backend.

## Root Cause

Two independent defaults that are each defensible alone but lethal together:

1. **A secret with a value in a data file is not a secret.** Unlike a
   `post_init_hook`-generated one, it is identical on every deployment,
   lives in git history forever, and survives `-u` (`noupdate="1"` only stops
   *overwrites*, it does not stop the *initial* install).
2. **A `_verify_*` fallback argument re-introduces the secret even after the
   parameter is deleted.** `get_param(key, default)` means "unconfigured
   silently means insecure" — the exact opposite of fail-closed.
3. **A webhook route resolves its gateway by `provider_type`, not by "the
   gateway this transaction actually used"** — so an inactive-in-spirit-but-
   active-in-DB stub stays reachable at its own URL.

The security of the whole money flow degrades to a manual go-live checklist item.
Checklists are not controls.

## Solution ✅

**1. Generate the secret per database, exactly like the JWT secret.**

```python
# hooks.py
import secrets

def post_init_hook(env):
    params = env['ir.config_parameter'].sudo()
    if not params.get_param('activity.webhook_secret'):
        params.set_param('activity.webhook_secret', secrets.token_urlsafe(64))
```

```python
# __manifest__.py
'post_init_hook': 'post_init_hook',
# and DELETE the <record> for the secret from data/ir_config_parameter.xml
```

**2. Make the accessor fail closed — no fallback argument, ever.**

```python
def _webhook_secret(self) -> str:
    secret = self.env['ir.config_parameter'].sudo().get_param('activity.webhook_secret')
    if not secret:
        # An unconfigured secret must break the gateway, not silently
        # accept a well-known key.
        raise UserError(_('The payment webhook secret is not configured.'))
    return secret
```

**3. Ship every dev/stub provider INACTIVE.** Let the operator activate it
deliberately — the same discipline a real gateway record already uses:

```xml
<field name="active" eval="False"/>
```

If checkout must work out of the box in a dev database, activate the stub from a
`demo:` file (never `data:`) — demo data is absent from production installs.

**4. Verify against the transaction's OWN gateway.** Resolve the gateway from
the referenced transaction rather than from the URL segment, so an unused-but-
active provider record is not an independently addressable entry point.

## ⚠️ Pitfalls

- `noupdate="1"` gives false comfort: it prevents a module *upgrade* from
  resetting an operator's edited value, but the record is still **created with
  the shipped value on first install**. It is not a mitigation.
- Rotating the parameter after go-live is **not enough** while the
  `get_param(key, default)` fallback is still in the code — delete the
  parameter (or a bad migration does) and you are back to the public key.
- Grep the whole addon for the literal, not just the accessor: test helpers and
  ops scripts (`Docs/test_*.py`, `build_golive_params.py`) often carry the same
  string and quietly document it for an attacker.
- Compare against how the *other* secret in the same codebase is handled. In the
  case that produced this entry, `activity.jwt_secret` was correctly generated in
  `post_init_hook` while `activity.webhook_secret` sat in a data file — the
  inconsistency is the tell. Audit every secret the module owns in one pass.
- Do not "fix" it by disabling the stub gateway only. The known secret also
  signs any *real* provider's webhook if that provider's verifier shares
  `_webhook_secret()`.

## Verification

```bash
# 1. No secret literal survives anywhere in the addon
grep -rn "dev-webhook-secret" addons/activity_payment/   # must be empty

# 2. Fresh install generates a unique, random secret
odoo-bin -d fresh_db -i activity_payment --stop-after-init
psql fresh_db -c "SELECT value FROM ir_config_parameter WHERE key='activity.webhook_secret';"
# -> a 64-byte urlsafe token, different on every database

# 3. Stub gateway is NOT live on a production-style install
psql fresh_db -c "SELECT name, active FROM activity_payment_gateway;"
# -> active = f

# 4. Deleting the parameter must break the webhook, not open it
psql fresh_db -c "DELETE FROM ir_config_parameter WHERE key='activity.webhook_secret';"
# -> POST /api/v1/payments/webhook/<provider> now returns an error, never 200
```

## References

- Related file: `security/portal-controller-sudo-browse-bypasses-record-rules-idor.md`
- Related file: `orm/money-flow-reversal-on-refund-cancel-reset-draft.md`
- Related file: `setup/neutralized-test-backup-in-production-reactivate-crons-from-source-defaults.md`
