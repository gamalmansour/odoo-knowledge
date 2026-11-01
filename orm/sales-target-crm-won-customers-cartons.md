# CRM Won Customers and Product Carton Targets in Sales Target Management

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | sale / orm / performance                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-06-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `sale.target`, `crm.lead`, `uom`, `performance`, `n+1`, `read_group`

---

## Problem

When tracking sales target achievements for sales representatives, two custom metrics were required:
1. **Product Carton Targets**: Setting targets for specific products in terms of cartons (secondary unit of measure) and calculating achievement by converting sold product quantities into cartons.
2. **New Customers Target**: Setting targets for the number of new customers acquired during the month. The criterion for a customer being "new" is that the salesperson has won a CRM Opportunity (`crm.lead` with state `won`) linked to that customer within the target date range.

A naive loop implementation fetching invoices and leads per salesperson would lead to massive **N+1 SQL query bottlenecks**, especially when displaying team hierarchies or rolling up target achievements.

## Root Cause

1. Standard target tracking defaults to basic revenue or visit counts.
2. Products have varying packaging (secondary UoMs with dynamic conversion factors), necessitating conversion calculations during aggregation.
3. Calculating new customers using customer creation date is inaccurate (customers might be created in one month but join/become active later). The CRM Opportunity status (`won_status == 'won'`) combined with `date_closed` is the true indicator of a won customer.
4. Performing nested `search` operations within a computed field loop generates high database load.

## Solution ✅

1. **Product Carton Line Model**: Created the model `sale.target.line` associated with `sale.target` with a unique constraint on product:
```python
class SaleTargetLine(models.Model):
    _name = 'sale.target.line'
    _description = 'Sales Target Product Line'
    _order = 'product_id'

    target_id = fields.Many2one('sale.target', string='Monthly Target', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    secondary_uom_id = fields.Many2one('uom.uom', string='Secondary UoM', related='product_id.secondary_uom_id', readonly=True)
    target_cartons = fields.Float(string='Target Cartons', required=True, default=0.0)
    achieved_cartons = fields.Float(string='Achieved Cartons', compute='_compute_achieved_cartons', store=False)
```

2. **Batch Querying & Performance Optimization**:
Using `_read_group` and pre-fetching invoice lines and CRM leads in a single query across the entire batch's date ranges, then mapping the values in-memory to prevent N+1 queries.

```python
    @api.depends('salesperson_id', 'date_from', 'date_to', 'target_amount', 'target_visit_count', 'target_new_customers', 'product_target_line_ids.target_cartons', 'company_id')
    def _compute_achievement(self) -> None:
        valid = self.filtered(lambda t: t.salesperson_id and t.date_from and t.date_to)
        # ... [Initialize arrays and dates] ...
        
        # 1. Fetch CRM Leads Won within target dates in a single search
        all_won_leads = self.env['crm.lead'].search([
            ('user_id', 'in', all_user_ids),
            ('won_status', '=', 'won'),
            ('date_closed', '>=', datetime_min),
            ('date_closed', '<=', datetime_max),
            ('partner_id', '!=', False)
        ])
        
        # 2. Map leads to user and date
        won_leads_map = defaultdict(list)
        for lead in all_won_leads:
            if lead.date_closed:
                won_leads_map[(lead.user_id.id, lead.date_closed.date())].append(lead.partner_id.id)
                
        # 3. Calculate carton quantities from posted invoice lines
        all_invoice_lines = self.env['account.move.line'].search([
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('move_id.state', '=', 'posted'),
            ('move_id.invoice_user_id', 'in', all_user_ids),
            ('move_id.invoice_date', '>=', min_date),
            ('move_id.invoice_date', '<=', max_date),
            ('product_id', '!=', False),
        ])
        # Group and divide in memory by secondary_uom_factor
```

3. **XML Views Integration**:
Added a new page/tab for the Product Carton Targets and integrated New Customers group fields under Personal and Team performance layouts using the `progressbar` widget.

## ⚠️ Pitfalls

- **Secondary UoM Factor Zero**: Ensure to check if the secondary UoM conversion factor (`secondary_uom_factor`) is set to `0` or `False`. Default to `1.0` in the Python calculation code to prevent `ZeroDivisionError`.
- **Date Matching**: CRM `date_closed` is a `Datetime` field, while the target's `date_from` and `date_to` are `Date` fields. Compare after converting dates (e.g. `lead.date_closed.date()`) to ensure timezone/time offsets do not miss matches.
- **Refunds Treatment**: Deduct refund quantities (`out_refund`) from carton achievements to accurately represent net carton sales.

## Verification

To verify the achievements, check the target details page in Odoo backend:
- Products added to target lines compute their achieved cartons by looking up posted invoice lines.
- CRM opportunities won by the salesperson are aggregated as partners on the target form.
- The upgrade log confirms the successful compilation of the models and XML views.

## References
- Related file: [views/sale_target_views.xml](file:///Users/gamal/odoo/odoo19.0/custom/sale_target/views/sale_target_views.xml)
- Related model: [models/sale_target.py](file:///Users/gamal/odoo/odoo19.0/custom/sale_target/models/sale_target.py)
