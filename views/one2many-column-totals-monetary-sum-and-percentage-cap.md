# One2many Column Totals: a Monetary `sum=` Needs the Currency Field, and a "Must Not Exceed 100%" Cap Needs `float_compare`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `tree`, `one2many`, `sum`, `monetary`, `currency_field`, `constraint`, `float_compare`, `percentage`

---

## Problem

Two things users ask for together on any schedule-of-payments style one2many (milestones, instalments, retention releases, allocation lines):

1. *"Total the amount column at the bottom."* The view already has `sum="Total"` on the monetary field, yet the footer shows nothing useful.
2. *"The percentages must never add up to more than 100%."* There is no declarative way to express it — `sum=` is presentation only and enforces nothing.

## Root Cause

**1. Monetary aggregation is currency-scoped.** A `Monetary` field carries a `currency_field` (default `currency_id`). The list renderer will not format an aggregate it cannot attach a currency to, so if the currency field is not one of the fields loaded in that same list view, the sum renders blank or unformatted. The trap is that the currency field is frequently a *related* on the parent (`related='contract_id.currency_id'`), so it exists on the model, works fine on the form, and is simply absent from the tree arch.

**2. `sum=` is a footer label, not a rule.** Nothing stops a user from typing 60 / 30 / 20. The cap has to be a model constraint.

## Solution ✅

**Make the monetary sum render** — add the currency field to the same list, hidden:

```xml
<tree editable="bottom">
    <field name="sequence" widget="handle"/>
    <field name="currency_id" column_invisible="True"/>   <!-- required for the Monetary sum -->
    <field name="name"/>
    <field name="percentage" sum="Total %"/>
    <field name="amount" sum="Total"/>
</tree>
```

Also add it (as `invisible="1"`) to any form that shows the monetary field, for the same reason.

**Enforce the cap in the model**, grouped by parent:

```python
from odoo.tools import float_compare

@api.constrains('percentage', 'contract_id')
def _check_percentage_total(self) -> None:
    for rec in self:
        if float_compare(rec.percentage, 0.0, precision_digits=2) < 0:
            raise ValidationError(_("Milestone '%s' cannot have a negative percentage.") % (rec.name or ''))
    for contract in self.mapped('contract_id'):          # one check per parent, not per line
        total = sum(contract.milestone_ids.mapped('percentage'))
        if float_compare(total, 100.0, precision_digits=2) > 0:
            raise ValidationError(_(
                "The milestones of contract \"%(contract)s\" add up to %(total).2f%%, "
                "which exceeds 100%%.\n\nReduce the milestone percentages by %(excess).2f%% before saving.",
                contract=contract.display_name, total=total, excess=total - 100.0,
            ))
```

## ⚠️ Pitfalls

- **Never write `if total > 100.0`.** A legitimate three-way split (33.34 + 33.33 + 33.33) does not land exactly on 100.0 in binary floating point, and a raw comparison rejects a perfectly valid schedule. `float_compare(total, 100.0, precision_digits=2)` is the fix, and it deserves a dedicated test.
- **Guard the sign too.** Without a `percentage >= 0` check, a negative line masks an over-100 schedule: 120 + (−25) sums to 95 and sails through while the real billing plan is nonsense.
- **Check the constraint against production data BEFORE shipping it.** A constraint on dirty data means users cannot save — or even fix — the offending records. Count first:
  ```sql
  select contract_id, count(*), round(sum(percentage)::numeric,4) total_pct
  from contract_milestone group by 1 having sum(percentage) > 100.0;
  ```
  Zero rows → safe to add. Non-zero → clean the data (or ship the constraint with a data-fix migration) first.
- **Iterate parents, not records.** `@api.constrains` fires on the modified lines, but the rule is about the sibling sum. `self.mapped('contract_id')` makes a 20-line edit cost one check instead of twenty, and correctly evaluates the post-write state.
- **Deleting is never blocked** — a cap only ever gets easier to satisfy when a line goes away, so no `unlink` override is needed. Worth a test so nobody "helpfully" adds one.
- **A cross-parent list view should not sum a percentage.** In a global "All Milestones" list, a percentage total across different contracts is meaningless — put `sum=` on the percentage only inside the parent form's one2many. (A monetary total across mixed currencies is equally meaningless, which is exactly why Odoo scopes the aggregate to the currency field in the first place.)

## Verification

```bash
./odoo-bin -c odoo17_dev.conf -d <db> -u construction_contract --test-enable --stop-after-init
```

Cover: total under 100 accepted, exactly 100 accepted, the 33.34/33.33/33.33 split accepted, create-over-100 blocked, edit-over-100 blocked, negative blocked, other parents not counted, reducing a line frees room, deleting a line frees room.

## References

- Implemented in `construction_contract` v17.0.1.8.0 — `models/contract_milestone.py`, `views/contract_owner_views.xml`, `views/contract_milestone_views.xml`, `tests/test_milestone_percentage.py` (11 tests)
- Related file: `views/tree-view-column-invisible-odoo17-18.md` — `column_invisible` is the Odoo 17+ spelling used above
- Related file: `performance/non-stored-compute-fields-in-list-and-search-views.md`
