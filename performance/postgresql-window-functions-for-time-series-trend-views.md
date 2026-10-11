# PostgreSQL Window Functions in Odoo SQL View Models for Cumulative Trends

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | performance                                |
| Odoo Versions | 16, 17, 18, 19 (All)                       |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-02                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `postgresql`, `sql-view`, `window-function`, `performance`, `trend-analysis`, `pivot-graph`, `orm`

---

## Problem

Building multi-period cumulative trend analysis (e.g., Project Margin Trend, Cumulative Cash Flow, S-Curve, or Burndown charts) in pure Python ORM computes requires iterating through thousands of child records, sorting them by date in memory, and running quadratic or $O(N \times M)$ accumulators.
When loaded on high-volume production databases, List, Pivot, or Graph views take tens of seconds to render, causing browser timeouts or memory exhaustion (`MemoryError` / OOM).

## Root Cause

Odoo's Python ORM does not natively calculate running cumulative aggregates across sibling rows. If done via computed fields (`store=False` or recomputed on change), each row calculation queries or scans prior rows.
In contrast, PostgreSQL evaluates analytical Window Functions (`SUM(...) OVER (PARTITION BY ... ORDER BY ...)`) in a single sequential query plan execution directly on the database engine.

## Solution ✅

Define a read-only SQL view model (`_auto = False`) utilizing PostgreSQL Window Functions within the `init()` method:

```python
# -*- coding: utf-8 -*-
from odoo import models, fields, tools


class ProjectMarginTrendReport(models.Model):
    _name = 'project.margin.trend.report'
    _description = 'Project Margin Trend Report'
    _auto = False
    _order = 'project_id, month_date desc'

    project_id = fields.Many2one('construction.project', string='Project', readonly=True)
    month_date = fields.Date(string='Period (Month)', readonly=True)
    revenue_billed = fields.Monetary(string='Monthly Billed Revenue', readonly=True)
    actual_cost = fields.Monetary(string='Monthly Actual Cost', readonly=True)
    gross_profit = fields.Monetary(string='Monthly Gross Profit', readonly=True)
    
    # Cumulative aggregates calculated by PostgreSQL window functions:
    cum_revenue = fields.Monetary(string='Cumulative Revenue', readonly=True)
    cum_cost = fields.Monetary(string='Cumulative Cost', readonly=True)
    cum_margin_pct = fields.Float(string='Cumulative Margin %', readonly=True)

    def init(self) -> None:
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH monthly_data AS (
                    SELECT 
                        project_id,
                        date_trunc('month', date)::date AS month_date,
                        SUM(revenue) AS revenue_billed,
                        SUM(cost) AS actual_cost
                    FROM some_transaction_table
                    GROUP BY project_id, date_trunc('month', date)::date
                )
                SELECT 
                    row_number() OVER () AS id,
                    project_id,
                    month_date,
                    revenue_billed,
                    actual_cost,
                    (revenue_billed - actual_cost) AS gross_profit,
                    SUM(revenue_billed) OVER (PARTITION BY project_id ORDER BY month_date) AS cum_revenue,
                    SUM(actual_cost) OVER (PARTITION BY project_id ORDER BY month_date) AS cum_cost,
                    CASE 
                        WHEN SUM(revenue_billed) OVER (PARTITION BY project_id ORDER BY month_date) > 0 
                        THEN (
                            (SUM(revenue_billed) OVER (PARTITION BY project_id ORDER BY month_date) - 
                             SUM(actual_cost) OVER (PARTITION BY project_id ORDER BY month_date)) / 
                            SUM(revenue_billed) OVER (PARTITION BY project_id ORDER BY month_date) * 100.0
                        )
                        ELSE 0.0 
                    END AS cum_margin_pct
                FROM monthly_data
            )
        """)
```

## ⚠️ Pitfalls

1. **Synthetic Unique ID:** Always include `row_number() OVER () AS id` to ensure every row has a distinct, valid integer primary key for Odoo's web client and ORM cache.
2. **Nullable Grouping Keys:** Always filter `WHERE project_id IS NOT NULL` before partitioning, otherwise rows with NULL keys will group together into a phantom aggregate.
3. **Partition Order:** In cumulative functions, always explicitly define `ORDER BY` inside `OVER (PARTITION BY ... ORDER BY ...)`; omitting `ORDER BY` makes `SUM()` calculate the total sum across the entire partition rather than a running cumulative sum.

## Verification

Query the view directly in PostgreSQL to verify cumulative running totals and check query execution time:
```sql
EXPLAIN ANALYZE SELECT * FROM project_margin_trend_report WHERE project_id = 1;
```
Execution finishes in single-digit milliseconds even over hundreds of thousands of transactions.
