# Neutralized ("for testing") backup restored into production — recover crons from SOURCE defaults, not a blanket UPDATE

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All (verified 19)                          |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `neutralize`, `ir.cron`, `backup`, `odoo-sh`, `production`, `mail-server`, `payment`, `webhook`, `migration`

---

## Problem

A database duplicated/downloaded **"for testing purposes"** is silently
**neutralized** by Odoo, and that state lives *inside the dump*. Restore that
dump as production (e.g. Odoo Online → Odoo.sh migration) and production ships
with: every scheduled action off, mail possibly blocked, payment providers
disabled, webhooks broken. Symptom: "كل الـ cron jobs وقفت" after go-live.

## Root Cause

Neutralization is per-module `data/neutralize.sql`. The important ones:

```sql
-- base/data/neutralize.sql
UPDATE ir_cron SET active = false          -- ALL crons except base.autovacuum_job
 WHERE id NOT IN (SELECT res_id FROM ir_model_data
                  WHERE model='ir.cron' AND name='autovacuum_job' AND module='base');
UPDATE ir_mail_server SET active = false;  -- + INSERT dummy 'invalid:1025' SMTP server
INSERT INTO ir_config_parameter ... ('database.is_neutralized', true) ...;
UPDATE ir_act_server SET webhook_url = 'neutralization - disable webhook' WHERE state='webhook';
-- mail: fetchmail off, push keys deleted; payment: providers disabled/test
```

Crucially it deactivates crons **without recording which were active before** —
so there is nothing in the DB to restore from.

## Solution ✅

**The source XML is the only truth left.** Every `ir.cron` is defined in module
data with a default `active` (absent field ⇒ True). Scan all addons paths for
`<record model="ir.cron">`, collect `(module, xmlid, default_active)`, and
generate SQL that re-activates exactly the default-active set:

```sql
CREATE TEMP TABLE _default_active_crons(module varchar, name varchar);
INSERT INTO _default_active_crons VALUES ('mail','ir_cron_mail_scheduler_action'), ...;
UPDATE ir_cron c
   SET active = true, nextcall = now() + interval '1 hour',
       failure_count = 0, first_failure_date = NULL
  FROM ir_model_data d
  JOIN _default_active_crons t ON t.module = d.module AND t.name = d.name
 WHERE d.model = 'ir.cron' AND d.res_id = c.id AND c.active = false;
```

Safe by construction: only installed modules (the `ir_model_data` join), never
activates by-design-inactive crons, `nextcall +1h` gives a review window before
anything fires. Solargy 19 numbers: 213 crons in source → 200 default-active,
13 default-off; on the dump 10→65 active, 11 correctly left off.

Run it on Odoo.sh: production branch → Shell → `psql < reactivate_crons.sql`.

## ⚠️ Pitfalls

- **Never blanket `UPDATE ir_cron SET active = true`** — some crons ship
  disabled by design, and several are **feature-toggled** (Odoo turns them on
  when the feature is configured): `base_automation` check, CRM lead assign,
  helpdesk auto-close, `sale.send_invoice_cron`, fetchmail service, payment
  post-process, EDI. Re-enable those manually only where the feature is used —
  a past `nextcall` (e.g. 2024) is the tell that one *used* to be active.
- **The 1-hour window matters:** reactivated mail-senders (Email Queue Manager,
  Digest, Followup, auto-invoice) will fire once the hour passes — check the
  outgoing queue and mail config first.
- **Check the other artifacts** — dump-dependent (this dump had none of them):
  dummy SMTP server `neutralization - disable emails`, `database.is_neutralized`
  param, `webhook_url='neutralization - disable webhook'`, and payment providers
  all forced `disabled` (this dump: 24/24 — re-enable only the used ones with
  live credentials).
- **Test the generated SQL on a copy first**: `createdb -T <dump_db> tmp` →
  apply → compare counts → drop.
- Prevention: production must only ever be restored from a **production**
  backup; the testing checkbox bakes neutralization into the dump itself.
- **Domain params survive the migration pointing at the OLD host** (separate
  from neutralization, verified on the same migration): `mail.catchall.domain`
  and the `mail.alias.domain` record keep the old Odoo Online domain
  (`*.odoo.com`), so customer replies route to the dead SaaS instance — fix via
  Settings → Technical → Email → **Alias Domains**; and set
  `web.base.url` + `web.base.url.freeze=True` or the first admin login rewrites
  it (a local restore shows up as `http://localhost:8020`).
- **A production copy restored locally has LIVE crons** — mail fails safely
  (`Connection refused`, no local SMTP) but IAP-backed crons (SMS queue,
  snailmail) go over plain HTTPS and can spend real credits from a dev machine.
  Neutralize local restores: `python odoo-bin neutralize -d <db>`.

## Verification

```sql
SELECT count(*) FILTER (WHERE active), count(*) FROM ir_cron;   -- expect ~65/76 here
SELECT id, name, smtp_host, active FROM ir_mail_server;          -- no 'invalid' dummy
SELECT key, value FROM ir_config_parameter WHERE key='database.is_neutralized';  -- 0 rows
```

## Related

- `setup/leftover-module-not-installable-skipped-cleanup.md` (same migration, test_performance leftover)
- `setup/odoo-silent-db-autocreate-masks-wrong-cluster.md`
