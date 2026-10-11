# Transient Model M2M Orphaned Rows Violate Foreign Key on Upgrade

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19, All                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-11                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `transientmodel`, `foreign-key`, `many2many`, `vacuum`, `crm.lead.lost`, `psycopg2.errors.ForeignKeyViolation`

---

## Problem

When upgrading a module that inherits or defines a `models.TransientModel` with a `fields.Many2many` relation to a regular model (for example inheriting `crm.lead.lost` which holds `lead_ids = fields.Many2many('crm.lead')`), Odoo's registry initialization fails during foreign key constraint checks:

```text
psycopg2.errors.ForeignKeyViolation: insert or update on table "crm_lead_crm_lead_lost_rel" violates foreign key constraint "crm_lead_crm_lead_lost_rel_crm_lead_lost_id_fkey"
DETAIL: Key (crm_lead_lost_id)=(6237) is not present in table "crm_lead_lost".
```

The entire Odoo server fails to boot or fails the module update process.

## Root Cause

`models.TransientModel` records (wizards) have a short lifespan and are regularly vacuumed/deleted by Odoo's built-in vacuum cron (`_transient_vacuum`). However, if an automatic `ON DELETE CASCADE` constraint was not enforced or was disabled during batch inserts or previous migrations, intermediate relation tables (such as `crm_lead_crm_lead_lost_rel`) retain rows pointing to deleted transient IDs.

When a module touching that wizard is reloaded or upgraded, Odoo runs `check_foreign_keys()` and attempts to execute:
```sql
ALTER TABLE "crm_lead_crm_lead_lost_rel" ADD FOREIGN KEY ("crm_lead_lost_id") REFERENCES "crm_lead_lost"("id") ON DELETE cascade;
```
PostgreSQL detects orphaned rows in `crm_lead_crm_lead_lost_rel` and blocks the table constraint with a fatal `ForeignKeyViolation`.

## Solution ✅

1. **Clean up orphaned relation rows from the database:**
```sql
DELETE FROM crm_lead_crm_lead_lost_rel 
WHERE crm_lead_lost_id NOT IN (SELECT id FROM crm_lead_lost);
```

2. **Proactive migration safeguard:**
If deploying updates to staging or production, include a pre-migration script in the module (`migrations/x.y.z/pre-migrate.py`):
```python
def migrate(cr, version):
    cr.execute("""
        DELETE FROM crm_lead_crm_lead_lost_rel 
        WHERE crm_lead_lost_id NOT IN (SELECT id FROM crm_lead_lost);
    """)
```

## ⚠️ Pitfalls

- Never assume TransientModel relation tables are empty or cleaned automatically by Postgres when foreign keys are evaluated during registry reload.
- Do not drop the relation table itself; only remove orphaned rows where the foreign key ID does not exist in the referenced transient table.

## Verification

Run the module update with test tags enabled:
```bash
./odoo-bin -c odoo.conf -d <db> -u <module_name> --stop-after-init
```
The registry will load and validate all foreign keys without error.
