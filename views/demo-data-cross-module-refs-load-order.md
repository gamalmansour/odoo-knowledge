# Demo Data Cross-Module Refs Fail Silently Due to Module Load Order

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `demo`, `load-order`, `depends`, `xmlid`, `ParseError`, `install`, `qa-checklist`

---

## Problem

A module's demo XML references records (or `ir.model` xmlids) from another module that is
**not in its `depends`**. The install does not crash — Odoo logs one warning and moves on:

```
WARNING ... Module construction_approvals demo data failed to install, installed without demo data
ValueError: External ID not found in the system: construction_contract.model_contract_progress_invoice
```

Worse, the failure **cascades**: every module whose demo references the failed module's demo
records also fails demo loading. In our case 2 root failures silently knocked out demo for
**23 of 29 modules** — `ir_module_module.demo` was `false` for all of them and every screen
was empty, while the install itself reported success (exit 0).

## Root Cause

Module load order is topological over `depends`. Demo data loads per-module inside a
savepoint at that module's position in the graph. A demo file referencing xmlids of a module
loaded LATER (or never) raises, Odoo rolls back just that module's demo (flag `demo=false`)
and continues. `-i` exit code stays 0, so CI that only checks the exit code sees green.

Also found the same class of bug in pre-existing demo: a field placed on the wrong model
(`boq_item_id` set on `contract.subcontractor` instead of its line model) had silently
disabled the whole suite's demo forever.

## Solution ✅

1. **Place cross-module demo in a module that depends on ALL referenced modules.**
   E.g. an `approval.chain` demo for `contract.progress.invoice` cannot live in the generic
   `construction_approvals` (depends: base, mail) — move it to `construction_contract`
   (which depends on `construction_approvals`, so the model exists at load time).
   Back-charges demo referencing `construction_project` demo subcontracts moved from
   `construction_backcharge` (depends: contract only) into `construction_developer`
   (depends on both).

2. **Verify with a clean-DB demo install and assert on the demo flag, not the exit code:**

```bash
dropdb --if-exists demo_verify
python3 odoo-bin -c conf -d demo_verify -i <all modules> --stop-after-init --log-level=info > install.log 2>&1
grep -c "demo data failed" install.log        # must be 0
psql -d demo_verify -c "SELECT name FROM ir_module_module WHERE name LIKE 'my_prefix_%' AND state='installed' AND NOT demo;"  # must be empty
```

3. To pre-generate computed data (e.g. cash-flow forecast lines) from demo, `<function>` tags
   work and run at demo-load time:

```xml
<function model="construction.project" name="action_compute_cashflow" eval="[ref('construction_project.demo_project_1')]"/>
```

## ⚠️ Pitfalls

- `grep "demo"` on an Odoo log matches every line (the db name is in each line) — grep for
  the literal `"demo data failed"`.
- Piping the install through `| tail` in CI throws away the traceback you need; log to a file.
- Equal-to-limit quantities pass `total > limit` constraints; off-by-one demo quantities that
  exceed BOQ limits will abort the module's whole demo, not just one record.
- The first module whose demo fails is the ROOT cause; every later "failed" module is usually
  just a cascade. Fix the first one and re-run before touching the rest.
