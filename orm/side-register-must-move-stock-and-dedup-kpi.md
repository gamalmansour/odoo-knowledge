# Side Registers (Waste/Loss/Damage) Must Move Real Stock and Dedup Against the Issue Flow

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All (verified on 17)                       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-02                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `stock`, `stock.scrap`, `kpi`, `double-counting`, `state-machine`, `anti-tamper`, `valuation`

---

## Problem

> A "register" model (waste log, damage log, loss report) that carries quantities and money but is **not wired to stock** creates three compounding integrity holes:
> 1. **Phantom stock** — waste is logged but on-hand qty never decreases, so book stock > physical stock and theft/shrinkage is undetectable.
> 2. **KPI double counting** — the same physical waste enters the KPI twice: once as a stock issue classified "wastage" and once as a register record.
> 3. **Free-text money** — `unit_cost` is manually typed and freely editable/deletable after the fact, so the wastage figure can be inflated, deflated, or rewritten.

## Root Cause

The register was designed as a reporting convenience, not a transactional document. Without a state machine, a stock move, and a dedup rule, every number in it is an unverifiable claim.

## Solution ✅

Full pattern implemented in `test_cons/construction_waste` (17.0.2.0.0):

1. **State machine** `draft → done → cancel` with a `write()` guard: business fields (`_LOCKED_FIELDS` frozenset) raise `UserError` once the record leaves draft, except via a `waste_workflow` context key used by the workflow methods themselves. `unlink()` allowed on draft only — confirmed records must be cancelled, preserving the audit trail.
2. **Two explicit source types**: `stock` (material still in the warehouse) vs `consumed` (material already issued). `stock` records, on confirm, check availability via `stock.quant._get_available_quantity()` (raise if insufficient — a waste record can never deduct more than physically there), then create + `do_scrap()` a `stock.scrap`, then overwrite `unit_cost` from `scrap.move_ids.stock_valuation_layer_ids` (real valuation, not manual input). State is set **last** (see `write-override-atomicity-pattern.md`).
3. **Dedup rule for the KPI**: `consumed` records may link a `material_issue_id`; the project KPI skips records whose linked issue is already classified `wastage` (the issue carries the cost). A constraint also caps total linked waste at the issued quantity (UoM-converted).
4. **Reversal on cancel** (see `money-flow-reversal-on-refund-cancel-reset-draft.md`): cancelling a confirmed stock record is manager-only and creates + validates a return transfer `scrap_location → source location` so book stock matches reality again. Reset-to-draft only from cancelled.
5. **Reclassification lock**: changing `consumption_type` on an already-issued material issue is manager-only (site engineers could otherwise hide waste by flipping it to "permanent").

## ⚠️ Pitfalls

- `_()` **kwargs**: `_("... %(source)s", source=...)` crashes with `TypeError: got multiple values for argument 'source'` — `source` is the name of GettextAlias's first positional parameter. Rename the placeholder.
- **Superuser bypass in shell tests**: `odoo shell` env is `su=True` (uid 1), so `if not self.env.su` guards silently pass and `unlink()` really deletes. Test guards with `env(user=env.ref('base.user_admin'))` or a purpose-built user.
- `stock.scrap.action_validate()` returns a **wizard action** when stock is insufficient instead of raising — check availability yourself with `stock.quant._get_available_quantity()` + `float_compare(precision_rounding=uom.rounding)` and call `do_scrap()` directly.
- Valuation layers legitimately yield 0 cost for products with 0 standard price/valuation — that IS the truth; do not fall back to the manual figure.

## Verification

```bash
# Does the register module even know stock exists?
grep -rn "stock.scrap\|stock.quant\|_get_available_quantity" custom/<module>/
```
Shell test: confirm a stock record → on-hand drops by exactly qty and unit_cost comes from valuation (set a wrong manual cost first and assert it was overwritten); edit/delete after confirm → UserError; confirm qty > on-hand → UserError; cancel as manager → on-hand fully restored via return picking; KPI unchanged when the record links a wastage-classified issue.

## References

- Related file: `orm/write-override-atomicity-pattern.md`
- Related file: `orm/money-flow-reversal-on-refund-cancel-reset-draft.md`
- Related file: `security/sod-approval-checks.md`
- Fixed in: `test_cons/construction_waste` (2026-07-02)
