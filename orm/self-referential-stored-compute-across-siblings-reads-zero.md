# A Stored Compute That Depends on the SAME Computed Field of Sibling Records Reads 0 — Source From Raw Fields Instead

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `store`, `recursion`, `siblings`, `running-balance`, `previous-record`

---

## Problem

A "previous certificate balance" pattern: each record needs a value from the *previous* record of the same model (running balances, prior-period figures, cumulative ledgers):

```python
mos_previous = fields.Monetary(compute='_compute_mos', store=True)

@api.depends('mos_line_ids.billable_amount',
             'contract_id.progress_invoice_ids.mos_current')      # ← the trap
def _compute_mos(self):
    for rec in self:
        rec.mos_current = sum(rec.mos_line_ids.mapped('billable_amount'))
        previous = ...siblings with id < rec.id...
        rec.mos_previous = previous[-1:].mos_current              # reads 0!
```

No error, no warning — `mos_previous` just silently computes as **0** whenever the trigger marks several siblings dirty at once (e.g. creating a new record invalidates `contract_id.progress_invoice_ids`, so ALL siblings enter the same recompute batch).

## Root Cause

`_compute_mos` both **writes** `mos_current` and **depends on** `mos_current` of sibling records. When Odoo recomputes, all dirty siblings are gathered into one protected compute set; reading a sibling's `mos_current` from inside the batch cannot trigger a nested compute (recursion protection), so it returns the field's default instead of the real value — depending on batch order it works in one test and returns 0 in the next.

## Solution ✅

Never chain sibling values through the computed field. Sum the **raw stored fields** the sibling's value is derived from:

```python
@api.depends('mos_line_ids.billable_amount', 'contract_id.progress_invoice_ids.state',
             'contract_id.progress_invoice_ids.mos_line_ids.billable_amount')  # raw lines
def _compute_mos(self):
    for rec in self:
        rec.mos_current = sum(rec.mos_line_ids.mapped('billable_amount'))
        previous = rec.contract_id.progress_invoice_ids.filtered(
            lambda i: i.state != 'cancelled' and i.id and rec.id and i.id < rec.id
        ).sorted('id')[-1:]
        rec.mos_previous = sum(previous.mos_line_ids.mapped('billable_amount'))  # from lines
        rec.mos_movement = rec.mos_current - rec.mos_previous
```

`billable_amount` on the line is computed only from the line's own fields — no cycle, deterministic in any batch order.

## ⚠️ Pitfalls

- The bug is **batch-order dependent**: single-record UI edits often look fine; test suites and imports (multi-record batches) expose it. If a running balance works in the form and zeroes in tests, suspect this.
- `mapped()` over a chain that ends in the same computed field is the same trap in disguise.
- If the raw source is too expensive to re-aggregate, the alternative is a **plain stamped field** written imperatively at a lifecycle point (create/confirm) — see the retention-bond stamp in the same module: `retention_bond_in_lieu` is stamped at IPC creation precisely so history is frozen and no live compute can rewrite it.
- Guard `i.id and rec.id` in the lambda: during some create paths siblings can carry NewId, and comparing NewIds orders records nonsensically.

## Verification

A test that creates TWO records in sequence and asserts the second one's "previous" figure — a single-record test cannot catch it.

## References

- Hit in `construction_contract` v17.0.1.10.0 — `contract.progress.invoice.mos_previous` (FIDIC 14.5 materials-on-site movement)
- Related file: `orm/freeze-stored-money-across-lifecycle-snapshot-and-lock-not-state-skip.md`
