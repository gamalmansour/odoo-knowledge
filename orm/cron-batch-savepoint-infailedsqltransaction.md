# Cron Batch Processing Aborted by InFailedSqlTransaction

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `ir.cron`, `transaction`, `savepoint`, `InFailedSqlTransaction`, `batch-processing`, `unique-violation`, `webhook`

---

## Problem

When manually triggering or automatically running a scheduled action (`ir.cron`) that processes batches of records (such as incoming webhooks, EDI files, or sync feeds), the execution crashes with:

```
psycopg2.errors.InFailedSqlTransaction: current transaction is aborted, commands ignored until end of transaction block
```

And in client RPC / UI:
```
RPC_ERROR: Odoo Server Error
  File "odoo/addons/base/models/ir_cron.py", line 121, in method_direct_trigger
    self.lastcall = fields.Datetime.now()
  File "odoo/fields.py", line 1424, in __set__
    records.write({self.name: write_value})
  File "odoo/addons/base/models/ir_cron.py", line 610, in write
    self._try_lock()
  File "odoo/addons/base/models/ir_cron.py", line 597, in _try_lock
    self._cr.execute(...)
psycopg2.errors.InFailedSqlTransaction: current transaction is aborted, commands ignored until end of transaction block
```

Even if the cron loop catches standard Python `Exception`, subsequent database writes fail immediately.

## Root Cause

1. In PostgreSQL, when an unhandled SQL error occurs (e.g. `psycopg2.errors.UniqueViolation` from a duplicate mapping or missing constraint), PostgreSQL puts the current transaction into an aborted state (`PQTRANS_INERROR`).
2. Even if Python code catches the exception (`except Exception:`), Python exception handling does **not** reset PostgreSQL's transaction state!
3. Any subsequent SQL query executed on that cursor within the same transaction will fail with `InFailedSqlTransaction`.
4. In `ir_cron.method_direct_trigger()`, after calling the cron method, Odoo updates `self.lastcall = fields.Datetime.now()`. Because the database transaction is aborted, `self.write()` attempts to run SQL (`self._try_lock()`), causing the fatal `InFailedSqlTransaction`.

## Solution ✅

### 1. Isolate Batch Record Processing with Savepoints

Every individual unit of work in a cron batch loop must run inside its own savepoint `with self.env.cr.savepoint():`. If that record fails, PostgreSQL safely rolls back only to that savepoint, preserving the outer transaction.

```python
# models/salla_webhook_log.py
for record in pending_logs:
    try:
        with self.env.cr.savepoint():
            record._process_single_payload()
            record.write({"state": "done", "error_message": False})
    except Exception as e:
        _logger.exception("Failed to process webhook log %s", record.id)
        # Use a new savepoint to safely record the error state
        try:
            with self.env.cr.savepoint():
                record.write({
                    "state": "error",
                    "error_message": traceback.format_exc(),
                })
        except Exception:
            _logger.exception("Failed to write error state for log %s", record.id)
```

### 2. Wrap Low-Level Unique/Insert Operations in Savepoints

When creating mapping records or lookup cache entries that could hit duplicate constraints (e.g., duplicate line items sharing the same remote product ID in one batch), always check first and wrap the creation in a savepoint:

```python
# models/wk_feed.py
existing_mapping = channel_id.match_product_mappings(channel_product_id)
if not existing_mapping:
    try:
        with self.env.cr.savepoint():
            channel_id.create_product_mapping(match, res_id, default_code)
    except Exception:
        # Avoid crashing if a concurrent transaction or duplicate line inserted it
        pass
```

## ⚠️ Pitfalls

- **Do NOT rely on Python `try...except Exception:` alone** for database operations in a loop. Without `with self.env.cr.savepoint():`, an SQL constraint violation leaves the transaction poisoned.
- **Do NOT commit (`cr.commit()`) inside a cron direct trigger** unless explicitly designed for chunked transactions, as it can cause unexpected locks or partial states if the user triggered it from a UI wizard/button.
- **Always log the traceback in a dedicated `error_message` text field** on the log record so errors are visible in the Odoo backend without digging through server logs.

## Verification

Run the cron directly in Odoo shell or UI with corrupted/duplicate data:
```python
cron = env.ref('sarha_salla_webhook.ir_cron_process_salla_webhook')
cron.method_direct_trigger()
```
The cron should finish with 0 errors, update `lastcall` successfully, and mark failing records as `state = 'error'` with individual tracebacks.
