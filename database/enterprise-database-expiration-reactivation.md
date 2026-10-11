# Enterprise Database Expiration Reactivation and Bypass

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | database / setup                           |
| Odoo Versions | 14, 15, 16, 17, 18, 19 (All Enterprise)    |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `database`, `enterprise`, `expiration`, `trial`, `ir_config_parameter`, `ir_cron`

---

## Problem

When an Odoo Enterprise test/development database reaches its trial or subscription expiration date, the web client completely locks out the user with a full-screen blocking overlay (`ExpiredSubscriptionBlockUI` with `.o_blockUI` class) or persistent warning banners.

```
This database has expired.
Register your subscription or buy a subscription.
```

## Root Cause

Odoo Enterprise checks the system parameter `database.expiration_date` in `ir_config_parameter` via `ir.http` during session initialization (`session_info`).
- When `daysLeft <= 0`, OWL component `ExpiredSubscriptionBlockUI` blocks the whole UI.
- Additionally, the scheduled action `Publisher: Update Notification` (`publisher_warranty.contract.update_notification`) periodically contacts Odoo warranty servers, resetting `database.expiration_date` and `database.expiration_reason` to `trial` or expired.

## Solution ✅

1. Update `database.expiration_date` in `ir_config_parameter` to a far future date (e.g., `2099-12-31 23:59:59`).
2. Remove `database.expiration_reason` from `ir_config_parameter`.
3. Deactivate the `Publisher: Update Notification` scheduled action in `ir_cron` to prevent automatic resets.

Execute via `psql`:

```bash
psql -d <database_name> -c "
UPDATE ir_config_parameter 
SET value = '2099-12-31 23:59:59' 
WHERE key = 'database.expiration_date';

DELETE FROM ir_config_parameter 
WHERE key = 'database.expiration_reason';

UPDATE ir_cron 
SET active = false 
WHERE cron_name = 'Publisher: Update Notification';
"
```

## ⚠️ Pitfalls

- **Do NOT leave the Publisher Warranty cron active:** If the cron runs, it will ping Odoo servers and overwrite `database.expiration_date` back to the expired date.
- **Ensure no quotes/syntax errors in date string:** The date must strictly adhere to the standard datetime format `YYYY-MM-DD HH:MM:SS`.

## Verification

Run the following SQL query to verify the updated expiration date and deactivated cron:

```bash
psql -d <database_name> -c "
SELECT key, value FROM ir_config_parameter WHERE key LIKE 'database.expiration%';
SELECT id, cron_name, active FROM ir_cron WHERE cron_name = 'Publisher: Update Notification';
"
```
