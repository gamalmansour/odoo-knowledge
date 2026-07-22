# Flipping a field to translate=True crashes ALL reads until the module is upgraded

**Category:** Deployment / ORM
**Date:** 2026-07-22
**Project:** activity (store, category name translation — client test server RPC_ERROR)

## Symptom
After deploying code that adds `translate=True` to an existing field (e.g. `product.category.name`), the server throws on ANY read touching that column — backend UI included:
```
psycopg2.errors.UndefinedFunction: operator does not exist: character varying ->> unknown
LINE 1: ... "product_category"."name"->>'en_US' ...
```
Looks scary (raw SQL error in the web client) but is purely a deploy-sequencing issue.

## Root cause
Odoo 17 stores translated fields as **JSONB**. The new registry emits `col->>'lang'` SQL, but the DB column is still `varchar` until the module **upgrade** runs `convert_column_translatable` (ALTER TABLE → jsonb, wrapping existing values under `en_US`). Code push + restart alone = registry and schema out of sync → every read of that column crashes. Reads can be triggered indirectly (e.g. product forms fetch the category's properties_definition row, which selects `name`).

## Fix (verified end-to-end locally)
Run the upgrade for the owning module on that DB:
```
odoo-bin -u activity_store -d <db> --stop-after-init
```
Verified: column flips `character varying` → `jsonb`, existing names preserved (readable via `->>'en_US'`), the crashing query succeeds. No data loss.

## Rule of thumb
Any change to a FIELD DEFINITION (translate, type, selection, required-with-default, new stored computed) is a schema change: the deploy note must say "upgrade module X" explicitly, and the symptom of skipping it is often a raw psycopg2 error in the WEB UI, not just the API. When handing off to a client who deploys by git-push + restart, list the exact `-u` modules every time.
