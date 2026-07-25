# Odoo 19 same-version ETL: merging a company's full history into another DB

## Metadata
- **Category:** Upgrade / Data Migration
- **Severity:** 🔴 Critical
- **Odoo Versions:** 19 (several points apply to 17/18)
- **Tags:** `migration`, `etl`, `multi-company`, `account.move`, `stock`, `fifo`, `jsonb`, `sequences`, `chatter`
- **Last Verified:** 2026-07-25
- **Author:** ENG/Gamal Mansour

## Problem ❌
Migrating a company's FULL history (config → partners → products → orders →
stock → moves → reconciles → chatter) from one Odoo 19 DB into an existing
multi-company Odoo 19 DB, with identical document numbers, states, amounts,
authors and dates — without the ORM "helping" and corrupting the copy.

## Solution ✅ (battle-tested playbook, Solargy UAE 2026-07)
Golden rule: **history is inserted, never executed.** Create via ORM only
when needed (drafts, names passed explicitly so no sequence draws), then SQL
writes the stored truth. Never call `action_confirm` / `_post` /
`aml.reconcile()` / `_action_done` on historical data.

1. **Company-keyed JSONB (17+):** `account_account.code_store`, category
   costing (`property_cost_method`…), partner properties, `standard_price` —
   rewrite key `"1"` → `"<new company id>"` via `jsonb_set`; one helper, or
   values silently fall back to defaults.
2. **v19 aml killer:** `debit`/`credit` are computed FROM `balance`
   (`_compute_debit_credit`). Creating invoice lines with debit/credit via
   `skip_invoice_sync=True` still zeroes ~98% of balances → after create,
   SQL-write `balance, debit, credit, amount_currency` verbatim on ALL lines
   (and the 8+ stored amount columns on moves + `payment_state`).
3. **v19 valuation:** SVL is gone; each `stock.move` carries stored `value`
   and FIFO is computed live from move history (`_run_fifo_get_stack`).
   Copy `value` verbatim → future COGS is bit-identical. `product.value`
   rows = manual revaluations → SQL INSERT (ORM create triggers a global
   revaluation). Quants = snapshot → SQL INSERT.
4. **Stored computes need a final word:** `picking.state`, SOL
   `qty_delivered`/`qty_invoiced`, POL `qty_received`, order totals (source
   may store `price_unit` beyond decimal precision — ORM rounds on create!)
   — end every phase with an idempotent SQL pass restoring SOURCE values.
5. **Delegation models** (`account.payment`, `account.bank.statement.line`):
   SQL INSERT pointing at the already-created `move_id` — ORM would post
   duplicate journal entries.
6. **Reconciles:** v19 `account_full_reconcile` is id-only; the exchange
   move sits ON the partial. Pure SQL insert under the aml mapping;
   `matching_number` is a plain Char — copy verbatim.
7. **Sequences:** `ir_sequence.number_next` LIES for implementation
   `standard` — read `SELECT last_value, is_called FROM ir_sequence_NNN`.
   account.move needs NOTHING (sequence.mixin infers from copied
   `sequence_prefix/number`). Create company-specific SO/PO sequences —
   Odoo prefers them over the shared global ones.
8. **Chatter:** polymorphic `(model, res_id)` remap through the full
   mapping registry; `mail.message.subtype`/activity types/ir.model.fields
   ids differ per DB — map via xmlid / (model, name). Never reuse a target
   record for two source ids (duplicate names exist: tags, categories,
   picking types).
9. **Cross-company matching traps:** match locations via the warehouse
   mapping FIRST (name search alone adopts the other company's same-named
   warehouse locations); match users by `lower(login)`; user/company
   partners are shared by design — map, don't duplicate.
10. **Safety harness:** sqlite id-mapping store (idempotent skip),
    batch commits, pg_dump snapshots before phase 1/8, and an assertion
    around every phase that the OTHER company's move count never changes.

## ⚠️ Pitfalls
- Creating a move line on a done stock move fires the quant engine — flip
  moves to draft, create lines, restore states via SQL.
- Creating an archived `res.users` force-archives its partner and the ORM
  rejects it — create active, then SQL-restore both states.
- SQL `WHERE NOT bool_col` excludes NULLs — use `IS NOT TRUE`.
- `message_main_attachment_id` on any copied row FK-crashes before
  attachments migrate — always drop it, backfill later if desired.
