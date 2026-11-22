# Odoo 19 Stock Valuation Report Must Use Native `is_in`/`is_out` and Signed `value` (Never `usage == 'internal'` or `abs(value)`)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `stock_account`, `stock.move`, `valuation`, `is_in`, `is_out`, `transit`, `odoo19`, `unit_cost`, `_get_valued_qty`

---

## Problem

Custom Odoo 19 stock valuation reports replacing the removed `stock.valuation.layer` model show large valuation discrepancies (e.g. >540,000 EGP drift) when deliveries pass through company-owned **transit locations** (such as delivery vehicles) or receipts target non-`internal` company locations, and risk inverting negative cost adjustments.

Typical symptoms:
- Deliveries from `Vehicle (transit) → Customers` are classified as `INTERNAL` with `0.00` value and hidden from the report.
- Internal loads from `WH/Stock (internal) → Vehicle (transit)` are misclassified as `OUT` with `0.00` value, cluttering the report.
- Receipts from `Vendors → Company View Location` valued by Odoo 19 (`is_in=True`) are hidden with `0.00`.
- Negative valuation adjustments (vendor credit note price variances, landed cost reversals) have their sign flipped positive by `abs(move.value)`.
- `unit_cost` computed as `abs(move.value) / move.quantity` mixes move UoMs with base-UoM costs, and `fields.Float` + `widget="monetary"` renders without currency symbol when `company_currency_id` is omitted from the `<list>` view.

## Root Cause

In Odoo 19 (`addons/stock_account/models/stock_move.py`):
1. `stock.valuation.layer` was removed; valuation lives directly on `stock.move` via stored booleans `is_in` and `is_out` (computed using `location._should_be_valued()` and `move_line._should_exclude_for_valuation()`), plus `value` (`Monetary`, currency `company_currency_id`).
2. `move.value` is stored **positive** for both incoming and outgoing moves (Odoo applies the minus sign only when reading outgoing valuation: `if self._is_out(): amount = -amount`). Applying `abs(move.value)` assumes Odoo ≤18 SVL negative values and silently flips legitimate negative adjustments.
3. Checking `location_id.usage == 'internal'` manually ignores company-owned `transit` locations (which Odoo's `_should_be_valued()` treats as company stock) and consignment exclusions.
4. `move.quantity` is in `move.product_uom`, whereas Odoo's valuation cost is per base UoM — the core helper is `move._get_valued_qty()`.

## Solution ✅

1. Compute direction and signed value strictly from Odoo 19's `is_in`, `is_out`, `state`, and `value` (without `abs()`):

```python
unit_cost = fields.Monetary(
    string='Unit Cost',
    currency_field='company_currency_id',
    compute='_compute_unit_cost',
    store=False,
)
total_value = fields.Monetary(
    string='Total Value',
    currency_field='company_currency_id',
    compute='_compute_valuation_fields',
    store=True,
    index=True,
)
move_type_label = fields.Selection(
    selection=[('IN', 'IN'), ('OUT', 'OUT'), ('INTERNAL', 'INTERNAL')],
    string='Move Type',
    compute='_compute_valuation_fields',
    store=True,
    index=True,
)

@api.depends('value', 'is_in', 'is_out', 'state')
def _compute_valuation_fields(self) -> None:
    for move in self:
        move_val = move.value or 0.0
        if move.state == 'done' and move.is_in:
            move.move_type_label = 'IN'
            move.total_value = move_val
        elif move.state == 'done' and move.is_out:
            move.move_type_label = 'OUT'
            move.total_value = -move_val
        else:
            move.move_type_label = 'INTERNAL'
            move.total_value = 0.0

@api.depends('value', 'is_in', 'is_out', 'is_dropship', 'state', 'quantity', 'product_uom',
             'move_line_ids.quantity_product_uom', 'product_id.standard_price', 'company_id')
def _compute_unit_cost(self) -> None:
    for move in self:
        valued_qty = move._get_valued_qty()
        if valued_qty:
            move.unit_cost = (move.value or 0.0) / valued_qty
        else:
            move.unit_cost = move.product_id.with_company(move.company_id).standard_price
```

2. In the `<list>` view and `ir.actions.act_window`:
   - Include `<field name="company_currency_id" column_invisible="1"/>`.
   - Use `options="{'currency_field': 'company_currency_id'}"` and `sum="Total Value"`.
   - Set action domain to `[('state', '=', 'done'), '|', ('is_in', '=', True), ('is_out', '=', True)]` and search filters to `('is_in', '=', True)` / `('is_out', '=', True)`.
   - Restrict the valuation menu with `groups="stock.group_stock_manager,account.group_account_readonly"` so regular warehouse users cannot bypass cost-hiding modules.

3. For historical stored rows already in production, ship a `<data noupdate="1">` idempotent `ir.actions.server` that recomputes only mismatched done moves via `env.add_to_compute(...)` + `flush_recordset(...)` (never mutate business data inside an upgrade hook).

## ⚠️ Pitfalls

- **Changing `Char` to `Selection`:** Keep the exact existing database values (`'IN'`, `'OUT'`, `'INTERNAL'`) as Selection keys so PostgreSQL needs zero migration and zero data loss.
- **`i18n/ar.po` without `#:` occurrences:** Odoo's `PoFileReader` silently skips every `.po` entry that lacks `#: model:...` / `#: model_terms:...` / `#: code:...` reference lines.
- **Forgetting `with_company(move.company_id)`** when falling back to `product_id.standard_price` leaks the wrong company's cost in multi-company databases.

## Verification

Compare the custom report net sum directly against Odoo 19 core valuation in SQL:

```sql
SELECT
    round(sum(CASE WHEN is_in THEN value WHEN is_out THEN -value ELSE 0 END)::numeric, 2) AS odoo19_core_net,
    round(sum(total_value)::numeric, 2) AS custom_report_net
FROM stock_move
WHERE state = 'done';
```

Both columns must match to `0.00` difference, and running the server action a second time must report `0 rows changed`.

## References

- Core implementation: `addons/stock_account/models/stock_move.py` (`is_in`, `is_out`, `_get_valued_qty`, `company_currency_id`)
- Core view: `addons/stock_account/views/stock_move_views.xml` (`stock_move_valuation_action`)
