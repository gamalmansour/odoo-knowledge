# Odoo: External Bot / JSON-RPC User-Scoped Execution (`with_user`) & Triple-Fallback Identity Linking

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-11-05                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `jsonrpc`, `with_user`, `hr.employee`, `res.users`, `telegram`, `access-rights`, `record-rules`, `create_uid`, `zero-trust`, `semantic-fingerprint`, `iso27001`

---

## Problem

When an external conversational or mobile bot (e.g., Telegram / WhatsApp / Voice ERP layer) connects to Odoo over `/jsonrpc` using a central service account (`uid`), two critical enterprise issues arise:

1. **Privilege Escalation & Admin Attribution (`Service Account Bypass`):**
   Every `execute_kw` call executes with the service account's privileges (`Administrator`), bypassing the employee's `ir.model.access` and `ir.rule` record rules, and stamping `create_uid = Administrator` instead of the employee's own `res.users` account.
2. **Failed Employee Onboarding When Telegram Uses `@username` or a Personal SIM:**
   Employees who hide their phone number behind a `@username` or whose Telegram account is registered on a personal SIM different from `hr.employee.mobile_phone` cannot be matched by phone number alone.

## Root Cause

1. Odoo's `/jsonrpc` (`object.execute_kw`) requires the user's password or personal API key if authenticating directly as each employee's `uid`, which is impractical and insecure to request inside a chat bot.
2. Relying solely on `hr.employee.mobile_phone` fails whenever an employee uses a different personal phone number on Telegram.
3. Adding custom linking fields (`secret_voice_chat_id`, `secret_voice_activation_pin`) to `hr.employee` without `groups="hr.group_hr_user"` triggers `AccessError` on `hr.employee.public` when non-HR users open employee profiles or Time Off.

## Solution ✅

### 1. Delegate RPC Execution to `with_user(emp.user_id)` on `hr.employee`
Add a server-side bridge method on `hr.employee` (with all custom stored fields protected by `groups="hr.group_hr_user"`):

```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    secret_voice_chat_id = fields.Char(groups='hr.group_hr_user', index=True, copy=False)
    secret_voice_telegram_username = fields.Char(groups='hr.group_hr_user', index=True, copy=False)
    secret_voice_activation_pin = fields.Char(groups='hr.group_hr_user', index=True, readonly=True, copy=False)

    def execute_voice_rpc_as_employee(
        self,
        target_model: str,
        method_name: str,
        args_list: list | None = None,
        kwargs_dict: dict | None = None,
    ):
        self.ensure_one()
        if not self.user_id:
            raise AccessError(_('Employee %s has no linked Odoo User.') % self.name)
        scoped_model = self.env[target_model].with_user(self.user_id).with_company(self.company_id)
        return getattr(scoped_model, method_name)(*(args_list or []), **(kwargs_dict or {}))
```

### 2. Triple-Fallback Identity Linking (`Phone` -> `@username` -> `One-Time Activation PIN`)
1. **Method A (Phone Button):** Use Telegram's `KeyboardButton(..., request_contact=True)` which returns the verified phone number even if the user hid their phone number in Telegram Privacy Settings.
2. **Method B (Automatic `@username`):** Match `update.effective_user.username` against `hr.employee.secret_voice_telegram_username` (or `work_email` local-part in Zero-Install mode).
3. **Method C (One-Time Activation PIN `SV-XXXXXX`):** Generate a 6-digit one-time PIN on `hr.employee`, and immediately clear (`secret_voice_activation_pin = False`) the PIN upon first verification so it cannot be replayed.

### 3. Zero-Trust Employee Archive Auto-Revocation (`ISO/SOC2`)
- Override `hr.employee.write`: when `vals.get('active') is False` (employee archived/resigned), automatically wipe `secret_voice_chat_id = False`, `secret_voice_activation_pin = False`, and `secret_voice_last_sync = False`.
- In `execute_voice_rpc_as_employee`: verify `self.active` and `self.user_id.active` before executing any RPC call.
- On the bot engine side (`verify_employee_still_active`), query `hr.employee` with `context={'active_test': False}` and immediately purge the employee's `chat_id` from the local identity cache (`registry.revoke_employee(chat_id)`).

### 4. Defeating Two-Angle Photo Fraud (`Semantic Invoice Fingerprint`)
- Binary `SHA-256` alone fails when an employee photographs the same paper invoice from two different angles or two different phones.
- Compute a deterministic **Semantic Invoice Fingerprint** (`SHA-256` of `Normalized Partner + Exact Amount + Invoice Date + Ref`) alongside a 30-day Odoo `account.move` duplicate scan (`partner_id` + `amount_total`).

## ⚠️ Pitfalls

- **Never omit `groups='hr.group_hr_user'`** on `hr.employee` identity/PIN/analytic fields or their XML view tags, or standard `base.group_user` employees will hit `AccessError` on `hr.employee.public`.
- **Self-Service Employees (`user_id = False`):** Employees in `hr.employee` who do not have a paid `res.users` seat must be restricted to self-service draft operations (e.g., leave requests or draft receipt submission) and blocked from financial inquiries (`treasury_pulse`) or posting entries (`action_post`).
- **Cached Bot Sessions After Resignation:** Never trust a local bot `chat_id` cache indefinitely without checking `active_test=False` on `hr.employee` / `res.users`.

## Verification

```bash
python3 -m unittest discover -s tests -v
```
