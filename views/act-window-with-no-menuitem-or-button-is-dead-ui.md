# An act_window / model with no menuitem and no button is dead UI — it ships but no user can reach it

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-16                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `act_window`, `menuitem`, `dead-code`, `audit`, `feature-list`, `security`, `qa`

---

## Problem

A module defines a complete, working model — fields, ACL rows in `ir.model.access.csv`, business
methods, sometimes even a sequence and demo data — and it looks finished in code review. But **no
user can ever open it**, because nothing routes to it:

- an `ir.actions.act_window` exists, but **no `<menuitem action="...">` and no `<button name="%(action)d">`** references it; or
- the model has **no view records at all**, so even a smart button would fall back to Odoo's auto-generated form; or
- a `TransientModel` wizard has an ACL row and a Python `action_*` that returns it, but **no form view and no button ever calls that method**.

Nothing raises. Nothing logs. The module installs green and the tests (if any) pass, because tests
call the methods directly and never go through the UI routing layer.

This surfaces late and expensively:

```
Client:  "Your feature list says the system tracks off-plan installments. Where is it?"
Reality: realestate.installment — model + invoice generation + overdue cron + ACL rows,
         zero views, zero act_window. Six months in the repo. Unreachable.
```

## Root Cause

Odoo's UI reachability is a **routing chain**, and each link is declared independently in a
different file:

```
menuitem (or button)  →  ir.actions.act_window  →  res_model  →  view records
```

Nothing validates the chain end-to-end. `ir.model.access.csv` grants permission on a model — it does
**not** imply the model is reachable. An `act_window` is just a record; an orphan one is as valid to
the ORM as a linked one. The module loader has no concept of "this action is unused", the way a
linker would flag an unreferenced symbol.

So "the code exists" and "the user can use it" are two independent facts, and only the first one is
enforced by the framework.

## Solution ✅

Audit the routing chain directly. For every `act_window` id, prove something references it:

```bash
cd /path/to/addons

# 1) Every act_window / server action id defined in the module
grep -rhoE 'id="(action_[a-z0-9_]+)"' --include=*.xml . | sed -E 's/id="(.*)"/\1/' | sort -u > /tmp/defined.txt

# 2) Every id actually referenced by a menuitem or a button
{ grep -rhoE 'action="([a-z0-9_.]+)"'      --include=*.xml . | sed -E 's/action="(.*)"/\1/'
  grep -rhoE 'name="%\(([a-z0-9_.]+)\)d"'  --include=*.xml . | sed -E 's/name="%\((.*)\)d"/\1/'
} | sed -E 's/^.*\.//' | sort -u > /tmp/referenced.txt

# 3) Defined but never referenced == dead UI
comm -23 /tmp/defined.txt /tmp/referenced.txt
```

Then for each model that should be user-facing, prove it has a view:

```bash
# A model with ACL rows but no ir.ui.view record anywhere is a red flag
grep -rl 'model="ir.ui.view"' --include=*.xml . | xargs grep -l 'your.model.name'
```

Fix by choosing deliberately — **do not just add a menu to silence the audit**:

- **Wire it** — add the `menuitem`/button if the feature is meant to ship, and QA it end-to-end.
- **Delete it** — if it was superseded (e.g. a wizard replaced by a header button doing the same job), remove the model, its ACL rows and its manifest entry. Dead code with ACL rows is attack surface for nothing.
- **Document it** — if it is genuinely internal (a mixin, an abstract base, a model only ever embedded as a `one2many` tab), say so in a docstring so the next audit does not re-flag it.

## ⚠️ Pitfalls

- **An ACL row is not reachability.** `ir.model.access.csv` is the single most misleading signal here — it makes a dead model look intentional and shipped.
- **A Python method returning an act_window dict is invisible to XML grep.** `action_view_x()` that builds `{'type': 'ir.actions.act_window', ...}` is real routing, but only if a *view* binds a button to it. Grep the method name in XML too, not just the action id.
- **`ir.actions.server` and `ir.actions.client` are not `act_window`.** A scan that only parses `model="ir.actions.act_window"` silently misses genuinely reachable dashboards (OWL client actions) and reports them as absent. Parse all three.
- **A commented-out `menuitem` still greps as a reference** if your pattern is naive — it will hide a real orphan. Strip XML comments first, or verify hits by eye.
- **`search_default_<x>: 1` in an action context silently does nothing** if the search view defines no `<filter name="x">`. Same class of bug: two independent declarations, no validation, no error.
- **Two act_windows for one screen.** A common accident is defining `action_foo` and `action_foo_menu` for the same model, wiring the menu to one and leaving the other orphaned. The orphan is harmless but pollutes the audit — and pollutes a client-facing feature list if you count actions instead of reachable screens.

## Verification

The chain is provable from the DB, which is stronger than grep (it resolves cross-module refs):

```python
# odoo shell -d <db>
Act = env['ir.actions.act_window']
Menu = env['ir.ui.menu']
used = set(Menu.search([('action', '!=', False)]).mapped(lambda m: m.action.id))
for a in Act.search([]):
    xid = a.get_external_id().get(a.id, '')
    if xid.startswith('construction_') and a.id not in used:
        # not menu-bound — now confirm no view binds a button to it
        print(xid, '->', a.res_model)
```

Any id printed must be justified by a button that opens it; otherwise it is dead.

## References

- Found while extracting a client-facing feature list from the 31-module `test_cons` construction
  suite (2026-07-16). Six real cases: `hse.ppe.type` (orphan act_window), `hse.penalty.wizard` (no XML
  at all), `contract.advance.receipt` (model + journal entries, no view), `realestate.installment`
  (+ cron, no view), `realestate.installment.wizard` and `realestate.cost.allocation.wizard` (ACL rows,
  no form, no action). All were excluded from the deliverable — a feature you cannot demo is not a
  feature you can sell.
- Related file: `views/invalid-action-window-target-inline.md`
