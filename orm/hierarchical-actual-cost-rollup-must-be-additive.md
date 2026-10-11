# Hierarchical actual-cost roll-up must be ADDITIVE — `if children: sum(children) else: own` drops direct costs on parent nodes

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-10                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `rollup`, `hierarchy`, `parent_store`, `money`, `wbs`, `boq`, `cost`

---

## Problem

A stored, recursive `actual_cost` on a hierarchical model (BOQ item / WBS / analytic tree)
is computed as *either* the children's roll-up *or* the node's own direct cost:

```python
if rec.child_ids:
    rec.actual_cost = sum(rec.child_ids.mapped('actual_cost'))   # parent: children ONLY
elif rec.execution_method == 'direct':
    rec.actual_cost = sum(completed_work_orders.mapped('total_cost'))  # leaf: own only
```

The moment a cost document (work order, invoice) is booked **directly on a node that also
has children**, its cost is **silently dropped**: the parent branch runs and never looks at
the node's own work orders. Real symptom: a 1700 work order booked on parent item `1.4`
(4 children) left `actual_cost = 0`. Users don't notice — the number just quietly under-reports.

## Root Cause

The `if children … else own …` structure treats "has children" and "has direct cost" as
mutually exclusive. In real cost control they are NOT: a summary node can carry its own
direct charges AND aggregate its children (SAP PS "account assignment element" postable at
any level; EVM control account = own budget/charges + work packages below).

## Solution ✅

Make the roll-up **additive** — own direct cost PLUS children:

```python
if rec.display_type:              # section/note rows carry nothing
    rec.actual_cost = 0.0
else:
    own = sum(rec.work_order_ids.filtered(lambda w: w.state == 'completed').mapped('total_cost'))
    own += sum(rec.subcontract_invoice_line_ids
               .filtered(lambda l: l.progress_invoice_id.state in ('approved', 'invoiced'))
               .mapped('current_amount'))
    own += sum(rec.child_ids.mapped('actual_cost'))
    rec.actual_cost = own
rec.variance = rec.budget_amount - rec.actual_cost
```

Leaf behaviour is unchanged (no children ⇒ `own` = its own cost); only parents gain their
previously-dropped direct cost. A cost document is linked to exactly ONE node, so it is
counted once and only rolls up through the parent chain — **no double counting**.

## ⚠️ Pitfalls

- **Recompute stored history on upgrade.** `actual_cost` is stored; changing the compute
  does NOT refresh existing rows. Ship a post-migration:
  `env.add_to_compute(recs._fields['actual_cost'], recs); env.flush_all()` (recursive=True
  makes Odoo process children before parents). See [[new-stored-field-feeding-subtractive-rollup-needs-backfill-migration]].
- **Budget vs actual asymmetry is expected.** Budget is usually bottom-up (parent = children
  roll-up, no independent parent line); actual can now land on the parent directly. The gap
  shows as variance at the parent — that's correct, not a bug.
- Keep the `display_type` (section/note) guard returning 0 — those rows must never carry cost.
- Progress/quantity computes that use the same `if children/else` shape may still ignore a
  parent's own execution — decide whether they need the same additive treatment.

## Verification

Test that a completed work order booked on a parent (with children) is counted, and that
`parent.actual = own + Σ(children)` with no double count. Confirm on a DB with history that
no `actual_cost` went negative and unrelated WBS/project totals are unchanged.

## References

- SAP: [post actual cost to a WBS element directly](https://community.sap.com/t5/enterprise-resource-planning-q-a/how-to-post-actual-cost-in-wbs-element-directly/qaq-p/739952)
- EVM control accounts: [Humphreys — EVM basics](https://www.humphreys-assoc.com/basic-concepts-of-earned-value-management-evm/)
- Related file: `orm/stored-compute-parent-stale-sequential-child-create.md`
