# Odoo 19 Alias Domain Stale Catchall Causes 'Address Not Found' Mail Bounce

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-06                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `email`, `mail.alias.domain`, `catchall`, `reply-to`, `bounce`, `microsoft-365`, `odoo19`

---

## Problem

When sending messages or job offers to external recipients from Odoo Chatter, the email is delivered to the recipient, but when the recipient clicks **Reply**, their email client addresses the reply to:
`catchall@<old-or-staging-database-name>.odoo.com`

The reply bounces immediately with the delivery error:
```
Address not found
Your message wasn't delivered to catchall@<database-name>.odoo.com because the address couldn't be found, or is unable to receive mail.
```

## Root Cause

1. In Odoo 17+, alias domain management was centralized in `mail.alias.domain`.
2. When a database is initialized, restored from backup, or migrated from a test URL (e.g. `solargy-e-mobility-co1.odoo.com`), `mail.alias.domain` retains the initial domain in record `id=1`.
3. In `res.company`, each company defaults to linking `alias_domain_id = 1`.
4. During email dispatch (`mail.thread._notify_get_reply_to_batch`), if `company.catchall_email` is set, Odoo overrides the `Reply-To` header of all notifications with `catchall@<alias_domain>`, completely ignoring the individual author's email (e.g., HR or sales user).
5. External mail servers (Microsoft 365 / Gmail) attempt to deliver the reply to that unrouted or non-existent Odoo domain, resulting in an unrecoverable `550 / Address not found` bounce.

## Solution ✅

### Option A: Direct Personal Reply-To (Recommended for Standard User Email)
If the company wants customer/candidate replies to go directly to the individual employee's inbox in Microsoft 365 / Outlook (e.g. `yasmin@company.com`):

1. Go to **Settings ➡️ Users & Companies ➡️ Companies**.
2. Open each active company record.
3. Locate the **Email Domain** (or **Alias Domain**) field and clear it (`False` / empty).
4. Save the company form.

> When `company.alias_domain_id` is empty, `company.catchall_email` evaluates to empty string, and Odoo's `_notify_get_reply_to` automatically falls back to `default=email_from` (the author's actual email address).

### Option B: Route Through Official Company Catchall
If replies must return to Odoo Chatter:

1. Go to **Settings ➡️ Technical ➡️ Email ➡️ Alias Domains**.
2. Open the existing alias domain record and update **Domain** to the actual company domain (e.g. `company.com`).
3. Ensure the Microsoft 365 admin creates a mailbox or distribution group for `catchall@company.com` and forwards incoming messages to Odoo's incoming mail server.

## ⚠️ Pitfalls

- **Replying to Old Messages:** Do not test the fix by clicking "Reply" on an email that was received *before* the configuration change. That email's headers already contain the old `Reply-To` value baked in. Always generate and send a fresh test message.
- **General Settings Dropdown Lock:** Clearing the Alias Domain field inside `General Settings` may not clear the underlying `res.company.alias_domain_id` if default compute logic triggers; explicitly clearing it on the `res.company` form directly ensures the relation is severed.
- **Empty User Partner Email:** If a user has `login` filled (e.g. `user@company.com`) but `res.partner.email` is empty (`NULL`), Odoo falls back to system notifications address. Always ensure both `login` and `res.partner.email` are populated.

## Verification

```bash
# Verify company catchall is empty so reply-to falls back to user email
psql -d <db_name> -c "SELECT id, name, alias_domain_id FROM res_company;"
```
When `alias_domain_id` is `NULL`, send an email from Chatter and inspect the outgoing email headers:
```bash
psql -d <db_name> -c "SELECT m.id, m.email_from, m.reply_to FROM mail_mail mm JOIN mail_message m ON mm.mail_message_id = m.id ORDER BY mm.id DESC LIMIT 1;"
```
Confirm `reply_to` matches the sender's individual email address.
