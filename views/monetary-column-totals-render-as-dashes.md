# Monetary Column Totals Render as Dashes When the Currency Field Is Unstored

| Field         | Value        |
|---------------|--------------|
| Category      | views        |
| Odoo Versions | 16, 17, 18   |
| Severity      | 🟡 Medium    |
| Last Verified | 2026-08-05   |
| Author        | ENG/Gamal Mansour |

**Tags:** `list-view`, `monetary`, `sum`, `currency_id`, `related-store`, `aggregation`

---

## Problem

Every money column in the project list carried a `sum=` attribute, and every total rendered
as an em dash:

```
Contract Value   Total Actual   Revenue Billed   Profit Margin
 16,272,000.00     508,600.00       825,000.00      316,400.00
  8,200,000.00   6,912,369.50             0.00   -6,912,369.50
       ...
        —              —                —               —        <-- the totals row
```

No error, no console warning, no server log. A portfolio list that cannot show portfolio
value — discovered only by opening the screen.

## Root Cause

A `Monetary` field renders through its `currency_field` (`currency_id` by default). The list
renderer refuses to aggregate a monetary column unless it can read that currency for the rows,
so the aggregate degrades silently to a dash.

Two separate conditions must both hold, and the first one is the trap:

1. **`currency_id` must be stored.** The usual definition is a plain related field:
   ```python
   currency_id = fields.Many2one(related='company_id.currency_id', string='Currency')
   ```
   With no `store=True` there is no column in the table, so the aggregate cannot resolve a
   currency. Confirm in SQL rather than trusting the model:
   ```sql
   \d construction_project
   -- no currency_id column => the field is not stored
   ```
2. **`currency_id` must be present in the same list view**, normally hidden:
   ```xml
   <field name="currency_id" column_invisible="1"/>
   ```

Adding the field to the view alone changes nothing while the field is unstored — which makes
this bug feel unfixable if you only try step 2.

## Solution ✅

```python
currency_id = fields.Many2one(
    related='company_id.currency_id', string='Currency', store=True,
    help="Stored because a Monetary column cannot render a column total unless its "
         "currency is readable from the database.")
```

```xml
<tree string="Projects">
    ...
    <!-- Monetary totals need the currency field in the same list. -->
    <field name="currency_id" column_invisible="1"/>
    <field name="contract_value" sum="Total Contract Value"/>
</tree>
```

Audit the whole codebase from the running database rather than by grepping XML — a summed
field may be Float (which aggregates fine without a currency), so only Monetary ones matter:

```python
for v in env['ir.ui.view'].search([('type', '=', 'tree')]):
    arch = etree.fromstring(v.arch_db or v.arch)
    sums = [f.get('name') for f in arch.iter('field') if f.get('sum')]
    M = env.get(v.model)
    monetary = [n for n in sums if n in M._fields and M._fields[n].type == 'monetary']
    names = [f.get('name') for f in arch.iter('field')]
    if monetary and not any(n and n.endswith('currency_id') for n in names):
        print(v.xml_id, v.model, monetary)
```

## ⚠️ Pitfalls

- **That query misses inline trees.** A `<tree>` nested inside a form's One2many is part of
  the *form* view record, not a `type='tree'` view, so filtering on `type='tree'` skips it.
  In this codebase the first audit found 13 list views; re-running it over **all** views and
  resolving each nested tree's model from the enclosing field's `comodel_name` found 6 more,
  including the BOQ grid on the project form — the most-looked-at total in the product.
  Walk up from the tree to the nearest `<field>` whose name is a One2many on the parent model.
- Adding `store=True` to a related field triggers a column creation and a full recompute on
  upgrade; harmless here but worth knowing on a large table.
- `column_invisible="1"` is the Odoo 17 spelling for list views; `invisible="1"` inside a tree
  still works but is deprecated for columns.
- Do not "fix" it by dropping the `sum=` attribute: the dash disappears but so does a total
  the user actually needs.

## Verification

Open the screen. This is not catchable from tests — `TransactionCase` never renders a view,
so a suite of 248 green tests said nothing about it.

```
$ 336,352,000.00   $ 57,237,590.18   $ 825,000.00   $ -56,412,590.18
```

## References

- Related file: `views/xpath-string-selector-not-allowed.md`
- Related file: `security/noupdate-group-change-never-reaches-existing-databases.md`
