---
title: Foreign Key Violation During Module Upgrade due to ondelete='restrict'
author: ENG/Gamal Mansour
date: 2026-06-29
category: Upgrade
tags: [upgrade, foreign-key, ondelete, restrict, psycopg2]
versions: [15, 16, 17, 18, 19]
---

# Foreign Key Violation During Module Upgrade due to ondelete='restrict'

## 🚨 Problem
During a module upgrade (e.g., `-u module_name`), the Odoo server crashes with a `psycopg2.errors.ForeignKeyViolation` error, and subsequently you might see `SerializationFailure` or `KeyError` on the database registry. 

This happens when a `Many2one` field has `ondelete='restrict'` and Odoo's ORM attempts to delete or clean up orphaned records (due to XML data updates, model structural changes, or view updates) that are still being referenced by the restricted field. Because of the `restrict` rule at the database level, PostgreSQL rejects the deletion, causing the upgrade script to halt midway, which leaves the registry in a broken state.

## 🛠️ Solution
1. **Python Model Update**: Review the model definitions and change `ondelete='restrict'` to `ondelete='cascade'` or `ondelete='set null'` on the affected `Many2one` field, depending on your business logic. 
2. **Manual DB Intervention**: Since the upgrade process parses models and immediately attempts database alterations, an existing broken registry might prevent Odoo from updating the constraint automatically. In this case, manually connect to the database and drop the constraint:
   ```sql
   ALTER TABLE target_table DROP CONSTRAINT target_table_field_id_fkey;
   ```
3. **Clear Stuck Processes**: A failed upgrade often leaves a hanging `odoo-bin` process. Ensure you kill all stuck processes (`ps aux | grep odoo-bin`) to prevent `SerializationFailure` before attempting the upgrade again.
4. **Retry Upgrade**: Run the upgrade command again (`odoo-bin -u module_name`). Odoo will rebuild the foreign key constraint with the correct `ON DELETE` behavior.

## ⚠️ Pitfalls
- Do **not** blindly change to `cascade` if the referenced records hold critical financial or accounting data (like `account.move.line`). Use `set null` instead, or handle the data migration cleanly in a pre-init hook.
- If you leave the stuck `odoo-bin` process running, your next upgrade attempt will timeout or fail with a concurrent update serialization error.
