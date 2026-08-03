# "Print the same columns I see on screen" — list optional-column state can't drive QWeb reports; use per-order switches

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All (verified 19)                          |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-08-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `qweb`, `report`, `optional`, `localStorage`, `sale`, `columns`, `display_discount`, `colspan`

---

## Problem

Client asks: *"the order-line list has optional columns I show/hide with the
⚙ selector — make the PDF print exactly the columns I currently see."*

## Root Cause (why the literal ask is impossible to do reliably)

`optional="show|hide"` toggles are saved in the **browser's localStorage
only** — the server never sees them. And the same QWeb report also renders
where no screen exists at all: **Send by Email**, the **customer portal**,
and scheduled/automated sends. Any screen-scraping approach (JS patch passing
localStorage into the report context) silently falls back to defaults in
those flows and breaks across upgrades.

## Solution ✅

Store the choice on the **record being printed**: per-order Boolean switches,
defaulting to on, each gated by relevance so empty columns never print:

```python
# sale.order
solargy_print_price_before_discount = fields.Boolean(default=True)
solargy_print_discount = fields.Boolean(default=True)          # the std Disc.% column
solargy_print_discount_amount = fields.Boolean(default=True)
solargy_print_net_price = fields.Boolean(default=True)
```

In the report inherit, derive one flag per column = *switch AND the order
actually has a discounted line*, and re-point the core `display_discount`
t-set so the standard Disc.% column follows its switch too:

```xml
<xpath expr="//t[@t-set='display_discount']" position="before">
    <t t-set="solargy_any_discount" t-value="any(l.discount > 0 for l in lines_to_report)"/>
</xpath>
<xpath expr="//t[@t-set='display_discount']" position="attributes">
    <attribute name="t-value">solargy_any_discount and doc.solargy_print_discount</attribute>
</xpath>
<!-- + t-sets solargy_show_before / _disc_amount / _net after it -->
```

Then per column: `<th t-if="solargy_show_X">` after the matching core `th`,
`<td t-if="solargy_show_X">` after the matching core `td` (guard the cell
content with `not collapse_prices` like core), **filler `<td t-if>` cells in
the grouped-section summary rows**, and widen BOTH `section_name_colspan` and
`td_combo_name`'s `t-att-colspan` with `+ (1 if solargy_show_X else 0)` terms.

## ⚠️ Pitfalls

- **Don't chase localStorage.** Email/portal/cron renders have no screen; the
  "same as my screen" ask must be re-anchored to a server-side source (per
  order, or company settings if one uniform layout is wanted).
- **AND each switch with data relevance** (`any(l.discount > 0 ...)`) or a
  checked switch prints an all-empty column on undiscounted quotations.
- **Forgetting the colspan xpaths misaligns section/combo title rows** — core
  computes them from `display_discount`/`display_taxes` only; every added
  column needs a `+1` term in both places, and a filler `<td>` in
  `tr_section_group` rows.
- xpath `//t[@t-set='section_name_colspan']` matches the FIRST of the two
  t-sets (the computed one) — the later `t-value="99"` full-width variant must
  stay untouched.
- Test by **rendering, not eyeballing**:
  `env['ir.actions.report']._render_qweb_html('sale.report_saleorder', ids)`
  then assert column headers in/absent per switch combination.

## Verification

`solargy_sale_lines` 19.0.1.2.0, fresh-DB install + 8/8 tests: default
switches print all columns on a discounted order; unchecking removes exactly
that column; an undiscounted order prints the clean standard table whatever
the switches say.

## Related

- `views/percentage-widget-ratio-behavior.md`
- `orm/state-gated-action-button-must-be-idempotent-for-rerun.md` (same
  "server-side source of truth" principle)
