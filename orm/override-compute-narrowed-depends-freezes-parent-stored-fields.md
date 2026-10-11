# Overriding a Stored Compute With a Narrowed `@api.depends` Silently Freezes ALL the Parent's Stored Fields

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `store`, `api.depends`, `inheritance`, `override`, `cross-module`, `staleness`, `money`

---

## Problem

> Module **B** inherits a model from module **A** and overrides a stored compute method (e.g. to add one extra term) — but re-declares `@api.depends` with only the NEW field. The override's `@api.depends` **replaces** the parent's dependency list for that method. The result: every stored field computed by that method now recomputes **only** when module B's narrow field changes, and **freezes** the moment any of the original (parent) inputs change. No error — the numbers just silently stop matching reality. Worst of all, the bug only appears **once module B is installed**, so module A's own tests pass and the regression ships invisibly.

```python
# construction_contract/models/contract_subcontractor_invoice.py  (module A — correct)
@api.depends('line_ids.current_amount', 'line_ids.cumulative_amount',
             'advance_recovery_percent', 'retention_percent',
             'contract_id.contract_value', 'retention_cap_percentage',
             'advance_payment_percentage')
def _compute_financials(self):
    # computes ~12 stored Monetary fields: net_payable, retention_amount,
    # advance_recovery_amount, net_principal_current, ...
    ...

# construction_hse/models/contract_subcontractor_invoice_inherit.py  (module B — BUG)
@api.depends('safety_deduction')          # <-- REPLACES the parent's depends entirely
def _compute_financials(self):
    res = super()._compute_financials()   # parent logic still runs...
    for inv in self:
        inv.net_payable -= inv.safety_deduction
    return res
# Once HSE is installed: editing BOQ quantities, retention % or advance %
# no longer recomputes the certificate. The IPC shows a stale certified amount.
```

## Root Cause

`@api.depends` is **per-method**, and when a subclass redefines the method, its decorator's dependency tuple becomes the *whole* trigger set for that method on the final (combined) model — the parent's tuple is **not merged in**. So a narrowed override turns a richly-triggered stored field into one that only fires on the narrow field. Because the stored column value is correct exactly once (at the next write that *does* touch `safety_deduction`), the drift is silent and there is no traceback.

## Solution ✅

> When you override a compute, you OWN the full dependency surface. Pick one:

```python
# A) BEST — don't subtract inside the shared compute at all. Model the new term as a
#    real LINE / field that participates in the parent's normal compute graph:
#    add `safety_deduction` to the parent's own @api.depends via a clean extension,
#    or make the penalty a deduction line on the IPC so net_payable already sees it.

# B) If you must override the method, re-declare the FULL parent depends + your field:
@api.depends('line_ids.current_amount', 'line_ids.cumulative_amount',
             'advance_recovery_percent', 'retention_percent',
             'contract_id.contract_value', 'retention_cap_percentage',
             'advance_payment_percentage',
             'safety_deduction')           # <-- parent's list, verbatim, PLUS the new one
def _compute_financials(self):
    super()._compute_financials()
    for inv in self:
        inv.net_payable -= inv.safety_deduction

# C) Compute the extra term in its OWN method/field and let the parent consume it,
#    so you never touch the parent's @api.depends.
```

## ⚠️ Pitfalls

- **The bug is invisible until the second module is installed.** Module A's unit tests stay green; only an integration DB with both modules reveals it. Always add a TransactionCase that installs both and asserts the field recomputes after a *parent* input changes.
- Same trap applies to **`compute=` reassignment, `inverse=`, and `search=`** on an overridden field, and to **`store`/`compute_sudo` mismatches** (see related entries — those make Odoo skip the DB column entirely).
- Don't "fix" it by calling `_compute_financials()` manually after writes — that only patches the paths you remembered; data imports, `write()` from other modules, and onchange will still leave it stale.
- A money/KPI field is the usual victim because it's the one people *trust* — a frozen `net_payable`/`retention` ships an incorrect payment certificate to a subcontractor.

## Verification

```python
# tests/test_subcontractor_ipc_recompute.py  (with construction_hse installed)
inv = self.env['contract.subcontractor.invoice'].create(vals_with_one_boq_line)
before = inv.net_payable
inv.line_ids[0].current_amount += 1000          # a PARENT input, not safety_deduction
self.assertNotEqual(inv.net_payable, before,    # fails today: frozen by narrowed depends
                    "net_payable must recompute when BOQ line amount changes")
```

## References

- Related file: `orm/stored-compute-incomplete-depends-silent-staleness.md`
- Related file: `orm/inconsistent-store-compute-sudo-computed-fields.md`
- Related file: `orm/compute_cache_warnings_ast.md`
- Found during the `test_cons` construction-suite audit (HSE override of `contract.subcontractor.invoice._compute_financials`).
