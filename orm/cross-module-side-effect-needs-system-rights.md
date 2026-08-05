# A Button That Side-Effects Into Another Module Must Run With System Rights — Otherwise It Rolls Back the User's Work

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-05                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `security`, `acl`, `sudo`, `cross-module`, `AccessError`, `workflow`, `uat`

---

## Problem

A user presses a perfectly ordinary button in *their* module and gets:

```
odoo.exceptions.AccessError: You are not allowed to create 'Owner Contract' (contract.owner) records.
```

The action *did* its own part (the tender was logged as won), then the automation reached into a neighbouring module — and because the whole method is one transaction, **everything rolls back**. The user sees a technical error and loses the work.

Found nine times in one UAT pass of a construction suite, always the same shape:

| Button (module) | Hidden side effect (other module) | Role that breaks |
|---|---|---|
| Mark as Won (tender) | creates `contract.owner` | Tender Manager |
| Activate (contract) | creates `construction.project` + BOQ | Contract Manager |
| Fetch BOQ (contract) | reads `project.boq.item` | Contract Manager |
| Complete (work order) | reads `purchase.order.line`, creates `stock.picking` + `account.move` | Site Engineer |
| Release Retention (DLP) | writes `contract.owner`, creates `account.move` | DLP Manager |

## Root Cause

ACLs are designed per module, per role — correctly. But **workflow automation crosses those boundaries**, and nobody re-checks the rights of the *pressing* role against the models the automation touches. It never shows up in unit tests, because `TransactionCase` runs as the superuser (see `backend/env-su-guard-silently-passes-in-transactioncase.md`) — the gap only appears when a real role presses the button.

## Solution ✅

Classify the side effect, then pick the mechanism:

**1. Automation / accounting side effect → system rights (`sudo`), with a comment saying why.**

```python
def action_mark_won(self):
    ...
    # as_system: awarding is a TENDER action; a tender manager is not required to hold
    # contract-creation rights. Without this the button raises AccessError and rolls
    # the whole award back, losing the user's work.
    contract = self._create_owner_contract_from_tender(as_system=True)
```

Keep the manual path unprivileged so a user creating the same record *by hand* is still checked:

```python
def _create_owner_contract_from_tender(self, vals=None, as_system=False):
    builder = self.sudo() if as_system else self
    contract = builder.env['contract.owner'].create(vals)
```

**2. Read-only lookup for a KPI or a default → `sudo()` on the search only.**

```python
# sudo: a READ of purchasing data to display a project KPI. Site engineers hold no
# purchase rights, yet this compute runs on any project read — including inside
# action_complete — so without it the whole completion fails.
po_lines = self.env['purchase.order.line'].sudo().search([...])
```

**3. Genuinely part of the job → grant the right explicitly via `implied_ids`.**

```xml
<!-- Site Engineer implies Inventory User: completing a work order ISSUES materials,
     which creates a stock.picking. That IS the engineer's job, so it is a real right,
     not something to hide behind sudo. -->
<field name="implied_ids" eval="[(4, ref('stock.group_stock_user'))]"/>
```

The dividing line: **is the user doing this thing, or is the system doing it because of what the user did?** Doing → grant the right. Consequence → `sudo`.

## ⚠️ Pitfalls

- **`implied_ids` sits in `noupdate="1"` data**, so editing the XML does **not** apply to existing databases. Ship a migration step or apply it manually:
  ```python
  env.ref('module.group_x').write({'implied_ids': [(4, env.ref('other.group_y').id)]})
  ```
- **Never blanket-`sudo` a whole action.** Sudo only the specific create/search that crosses the boundary, and comment the reason — otherwise you silently disable every rule the module has.
- **`sudo()` propagates through the recordset**, so `wizard.sudo().action_x()` covers everything `action_x` creates via `self.env` — useful, but check nothing user-scoped depends on the real uid inside.
- Returning a sudo'd record to the UI can raise on display; return it re-bound to the caller's env: `return contract.with_env(self.env)`.
- **Unit tests will not catch any of this.** Only a UAT pass with real roles (`with_user`) will.

## Verification

Drive each cross-module button with a user holding **only** its own module's role:

```python
mgr = env['res.users'].create({'name': 'Tender Mgr Only', 'login': 't',
    'groups_id': [(6, 0, [ref('base.group_user').id, ref('module.group_tender_manager').id])]})
assert not mgr.has_group('other_module.group_manager')
record.with_user(mgr).action_the_button()      # must not raise
```

## References

- Nine occurrences fixed across `construction_tender`, `construction_contract`, `construction_project`, `construction_dlp` during a four-stage UAT (tender → contract → execution → handover).
- Related file: `backend/env-su-guard-silently-passes-in-transactioncase.md`
