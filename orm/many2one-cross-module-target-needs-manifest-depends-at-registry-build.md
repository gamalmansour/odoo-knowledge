# A `Many2one` to a Model From an Undeclared Dependency Fails at Registry Build, Not Just at Runtime

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-08-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `fields`, `Many2one`, `depends`, `manifest`, `registry`, `api.depends`, `comodel_name`

---

## Problem

Adding an optional `Many2one` to a model from a module NOT in the current
module's `depends` — reasoning "it'll be fine, the target module is always
installed alongside this one in practice" — crashes the WHOLE registry at
`-i`/`-u` time, before any code runs:

```
WARNING ... odoo.fields: Field activity.payment.transaction.order_id with unknown comodel_name 'sale.order'
...
ValueError: Wrong @depends on '_compute_company_currency' (compute method of
field activity.payment.transaction.company_id). Dependency field 'company_id'
not found in model _unknown.
CRITICAL ... Failed to initialize database
```

## Root Cause

Odoo loads modules in **dependency-graph topological order**, not CLI
argument order. `activity_payment` had `order_id = fields.Many2one('sale.order',
...)` but its manifest `depends` list was `['activity_enrollment',
'account_accountant']` — no `sale`. Even though the actual `-i` command
installed `activity_store` (which pulls in `sale_management`/`sale_stock` →
`sale`) in the SAME run, `activity_payment` sits shallower in the dependency
graph and is registered FIRST. At that point `sale.order` does not exist in
the registry yet, so:

1. The field itself registers with a "floating" `comodel_name='sale.order'`
   (Odoo tolerates this at declaration time — the warning, not yet fatal).
2. Any `@api.depends(...)` chain that traverses THROUGH that field (here,
   `company_id`/`currency_id` computed off `subscription_id.company_id` OR
   `order_id.company_id`) tries to resolve `order_id`'s target model to look
   up `company_id` on it — and fails hard, because the target model
   genuinely doesn't exist in `_unknown` yet. This is a REGISTRY BUILD
   failure (breaks module install/update for every module in the graph),
   not a lazily-tolerated runtime gap.

Whether this reproduces depends on the SPECIFIC CLI module list determining
load order — a bare `-i activity_payment` (impossible here since nothing
else needs `sale.order`) wouldn't hit it, but the real multi-module install
(`-i activity_store,activity_payment,...`) does, because `activity_payment`
loads before `sale` regardless of argument order.

## Solution ✅

Add the module that actually DEFINES the target model to `depends` — even
if a "downstream" module in the same feature also depends on it and always
gets installed alongside. Prefer the smallest module that defines the
model, not a heavier one that merely extends it:

```python
# activity_payment/__manifest__.py
'depends': ['activity_enrollment', 'account_accountant', 'sale'],  # base
# sale.order lives in base `sale` — NOT sale_management/sale_stock (those
# only EXTEND it and are already pulled in by activity_store, which is a
# separate module one level up the graph).
```

## ⚠️ Pitfalls

- **This is a stricter rule than "cross-module model access needs a
  depends"** — that rule is about RUNTIME `self.env[...]` lookups
  (well-known). This is about the model's own FIELD DECLARATION needing the
  target model to exist at REGISTRY BUILD time, which is a strictly earlier
  point than any of that module's own code ever running.
- The `unknown comodel_name` WARNING alone is not fatal and easy to miss in
  a long install log — the fatal `ValueError` only appears once something
  (often an unrelated `@api.depends` chain, or a `related=` field) actually
  tries to resolve fields on the undeclared model. A field with NO
  dependent computed/related field touching it might silently install
  "successfully" with a dangling comodel and only break later when someone
  DOES add such a compute — don't rely on "it installed fine" as proof the
  depends is correct.
- Don't reach for `sale_management`/`sale_stock` reflexively just because
  a SIBLING module already depends on them — depend on the smallest module
  that actually defines the model you reference (here, base `sale`).
- Same family as the platform's existing sibling-module convention
  (`activity_payment`/`activity_store` previously never referenced each
  other, using guarded `'model.name' in self.env` runtime checks instead —
  see `orm/soft-optional-module-link-via-env-registry-check.md`). That
  pattern is for OPTIONAL cross-module integrations; a genuine field-level
  `Many2one` to another module's model is NOT optional and always needs a
  real manifest `depends` — the guarded-check pattern does not apply here.

## Verification

```bash
dropdb --if-exists test_db
python odoo-bin -c conf -d test_db --db-filter='^test_db$' \
  -i activity_store,activity_payment,activity_notification --test-enable \
  --test-tags /activity_store,/activity_payment,/activity_notification \
  --without-demo=all --stop-after-init --log-level=test
# Before fix: CRITICAL "Failed to initialize database" at module load,
#             before any test runs.
# After fix (added 'sale' to activity_payment's depends): registry builds
#             cleanly, tests run.
```

## References

- Code: `activity/activity_payment/__manifest__.py`,
  `activity/activity_payment/models/activity_payment_transaction.py`
  (`order_id` field + `_compute_company_currency`)
- Related file: `orm/soft-optional-module-link-via-env-registry-check.md`
  (the OPPOSITE case — optional integration, no depends, guarded runtime
  check — do not confuse the two)
