# Database Merge / Upgrade Leaves `stock.move.line` Stored Fields Stale → Validated Receipts Move ZERO Stock

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-26                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `upgrade`, `migration`, `merge`, `multi-company`, `stock.move.line`, `quantity_product_uom`, `stored-computed`, `related`, `stock.quant`, `silent-failure`, `valuation`

---

## Problem

> After merging two separate Odoo databases into one multi-company database (or after a
> version upgrade), the client reports: **"I validated a receipt but the quantities never
> showed up in the products."** The picking is `done`, the `stock.move` records show the
> right quantities, and Odoo raises **no error at all**. The stock simply never arrives.

Real case (Solargy, Odoo 19, 3 companies):

```
TOLL/IN/00067   state=done   3 moves: 20 + 20 + 40 units
  -> stock.move.quantity            = 20 / 20 / 40   ✅ correct
  -> stock.move.line.quantity       = 20 / 20 / 40   ✅ correct
  -> stock.move.line.quantity_product_uom = 0 / 0 / 0  ❌ THE BUG
  -> stock.quant for the Keyfob at TOLL/Stock: does not exist
```

Measured across the whole database:

| Company | done move lines | broken | units lost |
|---|---|---|---|
| 1 (Egypt, native to this DB) | 22,309 | **0** | — |
| 2 (UAE, merged in) | 838 | **794 (95%)** | **39,979** |

## Root Cause

Two `store=True` fields on `stock.move.line` were never recomputed by the merge/upgrade:

```python
# addons/stock/models/stock_move_line.py
quantity_product_uom = fields.Float(compute='_compute_quantity_product_uom', store=True)  # :40
state                = fields.Selection(related='move_id.state', store=True)              # :83
```

`quantity_product_uom` is **the field Odoo actually adds to the quants** — not `quantity`.
A line stuck at `0` therefore credits the warehouse with nothing.

The conversion itself is fine (`_compute_quantity_product_uom` just calls
`product_uom_id._compute_quantity(...)`, a 1:1 conversion when both UoMs match). The value
is **stale, not miscalculated** — which is why a recompute fully restores it.

**Why validating the picking did not fix it:** Odoo recomputes a stored field only when a
field in its `@api.depends` is written. Validation does not rewrite `quantity`, so the
compute never fired and `_action_done()` ran against the stale `0`.

**The timing signature that confirms the diagnosis** — compare `create_date` of the lines,
not the move date:

```
lines created BEFORE the upgrade  -> broken   (newest broken line: 2026-07-21)
lines created AFTER  the upgrade  -> healthy  (oldest healthy line: 2026-07-28)
```

⏰ **The dangerous consequence:** any document *created before* the upgrade but still
pending will move **zero stock the day somebody validates it** — the bug keeps producing
new damage long after the migration. In this case one landmine was still armed
(`TOLL/IN/00085`, 250 units).

## Solution ✅

Two separate steps. **Do not merge them** — one repairs the ledger, the other moves stock.

### Step 1 — Recompute the stale stored fields (moves NO stock)

```python
lines = env['stock.move.line'].sudo().search([('company_id', '=', target.id)])
# ... filtered to the actually-broken ones
for fname in ('quantity_product_uom', 'state'):
    env.add_to_compute(env['stock.move.line']._fields[fname], lines)
lines.flush_recordset(['quantity_product_uom', 'state'])
env.invalidate_all()
```

`add_to_compute` + `flush_recordset` writes the column directly. **This is deliberate:**
`stock.move.line.write()` re-synchronises quants for `done` lines
(`ml._synchronize_quant(...)`, stock_move_line.py ~line 495) and `stock_account` hooks the
same write to re-value the move — so writing through the ORM would silently correct stock
with **no visible inventory-adjustment document**. Repair the ledger first, correct stock
deliberately in Step 2.

### Step 2 — Reconcile the quants through the inventory-adjustment API

```python
quant = env['stock.quant'].with_company(company).with_context(inventory_mode=True)
quant.inventory_quantity = counted_qty
quant.action_apply_inventory()   # -> real stock.move -> _action_done() -> value -> journal entry
```

**Never** `quant.write({'quantity': x})`: `stock.quant.write` only guards
`product_id / location_id / lot_id / package_id / owner_id`, so `quantity` goes straight to
an `UPDATE` with no move, no valuation and no journal entry.

### Comparing quants to the ledger — get the query right

```sql
-- ✅ from stock_move_LINE, on the FULL quant key, in the PRODUCT's UoM
SELECT sml.product_id, sml.location_dest_id, sml.lot_id, sml.package_id, sml.owner_id,
       SUM(sml.quantity_product_uom)
  FROM stock_move_line sml JOIN stock_move sm ON sm.id = sml.move_id
 WHERE sm.state = 'done'
 GROUP BY 1,2,3,4,5
```

- from `stock_move_line`, **not** `stock_move` — quants follow the line's destination, which
  can differ from the move's;
- group on `lot_id / package_id / owner_id` too, or on a tracked product the total of every
  lot lands on the no-lot quant and **doubles the stock**;
- sum `quantity_product_uom`, **not** `quantity` — the latter is in the line's UoM.

## ⚠️ Pitfalls

- **Do not diagnose with the corrupted field.** Comparing quants against
  `SUM(quantity_product_uom)` *before* Step 1 makes the broken rows look correct on both
  sides and understates the damage (in this case 164 units instead of the real figure). Run
  Step 1 first, then measure.
- **`state` is corrupted too**, and it hides the scale: filtering move lines by
  `state='done'` returned 50 of 838 rows because 788 lines were stuck at `draft` while
  their move was `done`. **Join to `stock_move.state`, never trust the line's own.**
- **`picking_id` is a plain Many2one, not related** — 717 lines had it NULL. That is lost
  data, not a recompute candidate. Report it; do not "fix" it.
- **Odoo 19 removed `stock.valuation.layer`.** Valuation now lives on `stock_move.value`
  (plus a new `product.value` model for manual corrections). Any migration or audit code
  reading `stock.valuation.layer` breaks on 19.
- **Never force `is_storable = True`** to make a product adjustable — it permanently changes
  how that product is valued. Report it and let the client decide.
- **Refuse negative targets in internal locations.** `_apply_inventory` does not refuse
  them; a negative ledger balance means a missing opening receipt, which is a business
  decision.
- **Scope by a stable business key, not a company id.** Ids differ between production,
  staging and local restores; resolving the company by country + currency and asserting a
  single match prevents a stock correction from landing on the wrong legal entity.

## Verification

```sql
-- 1. No broken lines left (expect zero rows)
SELECT sml.company_id, count(*)
  FROM stock_move_line sml JOIN stock_move sm ON sm.id = sml.move_id
 WHERE sml.quantity > 0 AND COALESCE(sml.quantity_product_uom, 0) = 0
 GROUP BY 1;

-- 2. Line state agrees with move state (expect zero rows)
SELECT count(*) FROM stock_move_line sml JOIN stock_move sm ON sm.id = sml.move_id
 WHERE sml.state IS DISTINCT FROM sm.state;

-- 3. Step 1 moved no stock, Step 2 produced journal entries
SELECT sm.id, sm.reference, sm.quantity, sm.value
  FROM stock_move sm WHERE sm.is_inventory AND sm.date::date = CURRENT_DATE;

-- 4. The untouched companies really are untouched (compare before/after)
SELECT company_id, count(*), sum(quantity) FROM stock_quant GROUP BY 1;
```

Result on the real database: **796 → 0 broken lines**, the client's reported receipt
restored (Keyfob 0 → 20, Safety pin 10 → 30, Barrier 29 → 69 at TOLL/Stock), **5 journal
entries totalling 76,730.34 AED**, and the Egyptian company byte-identical before and after
(1,200 quants / 18,887.12 units).

## Delivery: wizard, not a shell script

A one-time shell script is tempting, but a module wins on three things that matter
for a repair touching stock and the ledger: it runs without SSH, it can be gated by a
**dedicated** security group (never `stock.group_stock_manager` — this posts journal
entries), and it leaves a **permanent, undeletable audit log** of who ran what, why,
and which entries came out.

Make it a **wizard, not a server action**. A server action is one button that does
everything; the whole point of this repair is *review before apply* — on the real data
**4 of 9 discrepancies had to be refused**, which a single-shot action cannot express.

Two implementation gotchas hit while building it, both already in this KB and both
confirmed accurate:

- `odoo-19-warnings.md` §7 — a search view's `<group>` takes **no attributes** in Odoo 19.
  `<group string="Group By">` is a hard `ParseError` at install.
- `calendar-privacy-...md` — **`env.flush_all()` before any raw SQL.** A test that
  corrupts a move line with a raw `UPDATE` right after `_action_done()` silently loses
  the corruption: pending computes flush afterwards and overwrite it. The symptom is a
  test that reports "nothing to repair".

Guard the phase separation in code, not in a comment: phase 1 snapshots
`SUM(stock_quant.quantity)` before and after and raises if it moved. If that ever
fires, the repair took the `write()` path and corrected stock behind the operator.

## Related

- `orm/stored-compute-incomplete-depends-silent-staleness.md` — same failure class, different trigger
- `orm/side-register-must-move-stock-and-dedup-kpi.md` — why stock corrections must produce real moves
- `security/multi-company-record-rules.md` — scoping work to one company
