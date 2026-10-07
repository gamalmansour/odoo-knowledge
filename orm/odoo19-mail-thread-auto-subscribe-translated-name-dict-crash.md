# Odoo 19 Mail Thread Auto-Subscribe Crash with Translated Partner Name

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo19`, `orm`, `mail.thread`, `res.partner`, `translated-field`, `auto-subscribe`, `portal`, `jsonb`, `formataddr`

---

## Problem

When creating records inheriting `mail.thread` (such as `sale.order`) programmatically, through a portal controller, or in automated backend flows, assigning a `user_id` (salesperson / representative) different from the current session user (`env.uid`) causes a fatal 500 error:

```python
Traceback (most recent call last):
  File "odoo/addons/mail/models/mail_thread.py", line 345, in create
    thread._message_auto_subscribe(create_values, followers_existing_policy='update')
  File "odoo/addons/mail/models/mail_thread.py", line 4822, in _message_auto_subscribe
    self.with_context(lang=lang)._message_auto_subscribe_notify(pids, template)
  File "odoo/addons/mail/models/mail_thread.py", line 4749, in _message_auto_subscribe_notify
    record.message_notify(...)
  File "odoo/addons/mail/models/mail_thread.py", line 3827, in <listcomp>
    formataddr((r['name'], r['email_normalized']))
  File "odoo/tools/mail.py", line 990, in formataddr
    name.encode(charset)
AttributeError: 'dict' object has no attribute 'encode'
```

## Root Cause

1. In Odoo 19, `res.partner.name` is a translatable column backed by a JSONB field (`{"en_US": "..."}`).
2. In `odoo/addons/mail/models/mail_followers.py`, `_get_recipient_data()` uses a raw SQL query `SELECT partner.name as name ...`.
3. In PostgreSQL, querying a JSONB column directly without extraction (`->>`) returns a Python dictionary (`{'en_US': 'Field Rep'}`).
4. When `_message_auto_subscribe_notify()` executes for a non-author portal user, `_notify_by_email_get_base_mail_values` processes `formataddr((r['name'], r['email_normalized']))`. Because `r['name']` is a dictionary instead of a string, calling `name.encode(charset)` crashes with `AttributeError: 'dict' object has no attribute 'encode'`.

## Solution ✅

When creating records programmatically or through controllers where automatic email notifications to newly assigned users are not desired (or when assigning portal representatives), always pass `mail_auto_subscribe_no_notify=True` in the context:

```python
order = request.env['sale.order'].sudo().with_context(
    mail_auto_subscribe_no_notify=True
).create({
    'partner_id': partner_id,
    'user_id': assigned_user.id,
    'company_id': request.env.company.id,
})
```

If email notification is explicitly required, ensure the recipient's name is properly cast or use `mail_create_nosubscribe=True` and follow up with a clean `message_post(partner_ids=[...])`.

## ⚠️ Pitfalls

- **Do NOT disable mail tracking globally:** Passing `mail_auto_subscribe_no_notify=True` only suppresses the automated email dispatch on assignment, preserving followers and chatter history.
- **Test with different users:** In unit tests, creating records where `user_id == env.user.id` hides this bug because Odoo does not notify the author of the record. Always test with a separate subordinate/rep user.

## Verification

Run the test suite with a dedicated supervisor creating an order for a subordinate portal user:

```bash
/path/to/odoo-bin -c custom.conf --test-enable --test-tags=/sale_visit:TestSupervisorCreateOrder --stop-after-init
```
Expected: 0 failed, 0 error(s).
