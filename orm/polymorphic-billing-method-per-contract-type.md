# Contract-Type-Driven (Polymorphic) Billing on One Invoice Line Model

**Category:** ORM
**Tags:** #orm, #billing, #construction, #computed-fields, #progress-invoice, #ipc, #money
**Severity:** 🔴 Critical
**Last Verified:** 2026-07-08
**Odoo Versions:** 17

## Problem
A single progress-invoice / IPC line model must bill differently depending on
the parent contract's pricing nature (Lump Sum, Unit Price / re-measurable,
Cost Plus, or Mixed) — but you don't want four separate models or a tangle of
`if contract_type == ...` scattered across compute, fetch, and views.

Naive traps that corrupt money:
- Computing `current_amount = qty × price` for ALL types (a Lump-Sum contract
  then gets billed by re-measured quantities instead of progress %, and Cost
  Plus never applies the fee).
- Carrying only `previous_qty` forward across periods. Lump-Sum needs
  `previous_pct` and Cost Plus needs `previous_cost` — seed only qty and the
  cumulative baseline silently resets to 0 every period, so each IPC re-bills
  from scratch (massive over-billing) or shows 0% done.

## Solution ✅
**1. A single resolver field** `billing_method` (stored compute) on the invoice
line, mapping the contract type to a per-line method; for `mixed`, defer to a
per-line `billing_method` on the source BOQ line:

```python
@api.depends('progress_invoice_id.contract_id.contract_type', 'boq_line_id.billing_method')
def _compute_billing_method(self):
    for rec in self:
        ct = rec.progress_invoice_id.contract_id.contract_type
        rec.billing_method = (rec.boq_line_id.billing_method or 'unit_price') if ct == 'mixed' else (
            ct if ct in ('lump_sum', 'cost_plus') else 'unit_price')
```

**2. One `_compute_amounts` that branches on `billing_method`** — keep separate
input fields per method (`current_qty` / `current_pct` / `current_cost`) plus a
stored `line_value = total_qty × unit_price` as the Lump-Sum base:

```python
if method == 'lump_sum':
    rec.current_amount    = (rec.current_pct / 100.0) * rec.line_value
    rec.cumulative_amount = ((rec.previous_pct + rec.current_pct) / 100.0) * rec.line_value
elif method == 'cost_plus':
    markup = 1.0 + rec.cost_plus_fee_pct / 100.0
    rec.current_amount    = rec.current_cost * markup
    rec.cumulative_amount = (rec.previous_cost + rec.current_cost) * markup
else:  # unit_price
    rec.current_amount    = rec.current_qty * rec.unit_price
    rec.cumulative_amount = (rec.previous_qty + rec.current_qty) * rec.unit_price
```

**3. Method-aware cumulative seeding in the "fetch BOQ" action** — build three
prior maps (qty, pct, cost) from prior non-draft IPC lines and seed only the one
the line's method needs. The header `gross = sum(current_amount)` and all the
downstream deductions stay untouched because each line already resolves its own
amount.

**3b. Cost Plus auto-seeds actual cost from the execution project.** Rather than
manual entry, seed `current_cost` as the delta of the linked project's real
incurred cost: `max(cumulative_actual_cost - previous_cost, 0)`. The actual cost
already lives on `project.boq.item.actual_cost` (completed work orders at real
stock-valuation cost + approved subcontract invoices) and links back via
`contract_boq_line_id`. Key safety point: `contract_boq_line_id` is set ONLY on
the top-level project item (its `actual_cost` already rolls up breakdown
children), so summing the search result does NOT double count. Keep the field
editable (auto + manual override) and it naturally falls back to 0 → manual when
no project is linked. Verified end-to-end: WO cost 1600 → IPC1 current_cost 1600,
amount 1760 (×1.10); period 2 cumulative 2400 → IPC2 delta 800, amount 880;
manual override and no-project fallback both hold.

**4. Views:** cell-level `invisible="billing_method != 'unit_price'"` (NOT
`column_invisible`) so a Mixed contract can show qty inputs on one row and %
inputs on the next in the same tree. Show `cost_plus_fee_percentage` only when
`contract_type in ('cost_plus','mixed')`; show the per-line `billing_method`
column only when `parent.contract_type == 'mixed'`.

**5. Guard rail:** `@api.constrains` blocking cumulative Lump-Sum % > 100 and
negative qty/%. Money code must refuse to over-certify.

## Verification (all rolled back)
Per-type single-period: Unit 30×2000=60,000 · Lump 20%×500k=100,000 · Cost
50,000×1.12=56,000 · Mixed 150k+10k+22k=182,000. Multi-period Lump: IPC1 40%,
IPC2 seeded previous_pct=40, +35% → cumulative 375,000 (75%); >100% blocked.

## ⚠️ Pitfalls
- Keep the three period inputs as separate fields; overloading one `current_x`
  field per method makes the view and constraints ambiguous.
- `line_value` must be **stored** — Lump-Sum billing reads it every period; a
  non-stored version recomputes fine but can't be summed/grouped in lists.
- Don't forget the fee is a **contract-level** field surfaced on the line via a
  `related` so the compute and the view can both see it.
