# Odoo 19 CLI `db load -f -n` Wipes Local Filestore on `_nofs.zip` Restores & Shell Password Verification

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 18, 19                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-15                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `db load`, `nofs`, `filestore`, `neutralize`, `res.users`, `password`, `odoo-bin shell`

---

## Problem

1. When refreshing a local database from an Odoo.sh `_nofs.zip` backup (which contains `dump.sql` and an empty `filestore/` directory) using `odoo-bin db -c <conf> load -f -n <db> <dump_nofs.zip>`, passing `-f` (`--force`) invokes `odoo.service.db.exp_drop(<db>)`, which **deletes `<data_dir>/filestore/<db>`** and replaces it with an empty directory — wiping previously cached SHA1 attachments, company logos, and compiled web assets.
2. When resetting the `admin` (`id=2`) password inside `odoo-bin shell` and immediately testing login via `env['res.users']._check_credentials(...)`, Odoo raises `odoo.exceptions.AccessDenied` even though the password was saved properly.

```
odoo.exceptions.AccessDenied: Access Denied
```

## Root Cause

1. `odoo/cli/db.py` (`Db.load`) calls `exp_drop(target)` when `--force` is enabled. Because Odoo's filestore is content-addressed by SHA1 (`store_fname = ab/<sha1>`), keeping the existing filestore directory across incremental `_nofs.zip` restores preserves all unchanged files automatically.
2. `odoo-bin shell` initializes `env` with `uid = 1` (`__system__` / OdooBot, whose password is `NULL`), whereas `_check_credentials` validates against `self.env.user`. Calling `env['res.users']._check_credentials(...)` without `.with_user(2)` checks `uid=1` instead of `admin` (`uid=2`).

## Solution ✅

```bash
# 1. Preserve existing content-addressed filestore before -f drops it
if [ -d "<data_dir>/filestore/<db>" ]; then
  mv "<data_dir>/filestore/<db>" "<data_dir>/filestore/<db>_prev_bak"
fi

# 2. Drop, restore, regenerate UUID (copy=True by default), and neutralize crons/mail/webhooks
./odoo-bin db -c <conf> load -f -n <db> "<path_to_nofs_backup.zip>"

# 3. Restore preserved filestore
if [ -d "<data_dir>/filestore/<db>_prev_bak" ]; then
  rm -rf "<data_dir>/filestore/<db>"
  mv "<data_dir>/filestore/<db>_prev_bak" "<data_dir>/filestore/<db>"
fi

# 4. Reset admin (id=2) password, set local web.base.url, and verify with .with_user(2)
./odoo-bin shell -c <conf> -d <db> --no-http << 'EOF'
admin = env['res.users'].browse(2)
admin.password = '1'
if admin.totp_secret:
    env.cr.execute("UPDATE res_users SET totp_secret = NULL WHERE id = 2")
env['ir.config_parameter'].sudo().set_param('web.base.url', 'http://localhost:1919')
env.cr.commit()

# Scope to uid=2 when verifying credentials in shell
assert env['res.users'].with_user(2)._check_credentials(
    {'type': 'password', 'password': '1'}, {'interactive': True}
)['uid'] == 2
EOF
```

## ⚠️ Pitfalls

- **Never pass `--move` on local developer restores:** Omitting `--move` keeps `copy=True`, which generates a fresh `database.uuid` and `database.secret` so the local copy never collides with the client's live Odoo Enterprise subscription.
- **Always pass `-n` (`--neutralize`):** Deactivates `ir.mail_server`, scheduled `ir.cron` jobs, payment providers, and external webhooks before starting the local server.
- **PostgreSQL 16.10+ / 18 `\restrict` meta-command:** Recent Odoo.sh dumps include `\restrict <token>` on line 1 (CVE-2025-8714). Ensure `pg_path` in `<conf>` points to PostgreSQL 16.10+ / 17.6+ / 18+ `bin` so `psql` recognizes `\restrict`.

## Verification

```bash
./odoo-bin shell -c <conf> -d <db> --no-http << 'EOF'
print(env['res.users'].with_user(2)._check_credentials({'type': 'password', 'password': '1'}, {'interactive': True}))
print("Neutralized:", env['ir.config_parameter'].sudo().get_param('database.is_neutralized'))
EOF
```

## References

- Related file: `setup/upgrade-odoo-com-dump-has-no-filestore.md`
- Related file: `setup/neutralized-test-backup-in-production-reactivate-crons-from-source-defaults.md`
