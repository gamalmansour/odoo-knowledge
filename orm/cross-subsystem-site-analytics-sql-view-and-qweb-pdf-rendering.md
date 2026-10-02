# Cross-Subsystem Site Analytics SQL View & QWeb PDF Document Design

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `analytics`, `sql-view`, `cube`, `qweb-pdf`, `reporting`, `flush_all`, `unhashable-list`, `odoo18`

---

## Problem

When building executive multi-subsystem analytics dashboards and official PDF documents (e.g., Daily Site Reports combining Manpower, Heavy Fleet Fuel, Ready-Mix Concrete Pours, Compressive Cube QA/QC Tests, and Subcontractor Backcharges), developers encounter two severe issues:

1. **SQL Analytical View Returns 0.0 in Unit Tests or New Transactions:**
   After creating ORM records (`project.daily.report`, `construction.equipment.fuel.log`, etc.) and immediately querying the `_auto = False` view (`construction.site.operations.dashboard`), numeric metrics (such as `labor_hours` or `fuel_quantity_liters`) return `0.0`, causing test assertion failures:
   ```
   AssertionError: 0.0 != 120.0
   ```

2. **QWeb PDF Report Rendering Raises `TypeError: unhashable type: 'list'`:**
   Attempting to programmatically test or generate PDF bytes via `report._render_qweb_pdf(rec.ids)` raises:
   ```python
   Traceback (most recent call last):
     File ".../odoo/tools/lru.py", line 33, in __getitem__
       a = self.d[obj]
   TypeError: unhashable type: 'list'
   ```

---

## Root Cause

1. **ORM Write Cache Isolation from Database Views:**
   Models with `_auto = False` are backed by raw PostgreSQL `CREATE OR REPLACE VIEW`. Standard Odoo ORM methods (`search`, `read_group`) execute raw SQL against the PostgreSQL engine. Newly created ORM records during a transaction remain in Python memory cache or dirty queue until explicitly flushed. Because the SQL view bypasses the ORM write buffer, PostgreSQL queries run against tables that have not yet received the flushed rows.

2. **`ir.actions.report._render_qweb_pdf` Method Signature:**
   In Odoo 16, 17, and 18, the method signature is:
   ```python
   def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
   ```
   The first parameter `report_ref` is the report action identifier (either a browse record `ir.actions.report` or an XML ID string like `'module.action_report_name'`). Calling `rep._render_qweb_pdf(rec.ids)` mistakenly passes the list of integer IDs as `report_ref`. When the report cache attempts `self._get_report(report_ref)`, it attempts to use the list `[rec.id]` as a cache key in an LRU dictionary, triggering `TypeError: unhashable type: 'list'`.

---

## Solution ✅

### 1. Robust Multi-Subsystem CTE SQL View with Typed Keys

When combining multiple subsystems that may occur on different dates or projects, synthesize a complete union of keys using CTEs, and explicitly cast `NULL` columns to prevent PostgreSQL type collation errors:

```python
class ConstructionSiteOperationsDashboard(models.Model):
    _name = 'construction.site.operations.dashboard'
    _description = 'Executive Site Operations Analysis Cube'
    _auto = False
    _order = 'date desc, project_id'

    project_id = fields.Many2one('construction.project', string='Project', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    concrete_volume = fields.Float(string='Concrete Poured (m³)', readonly=True)
    fuel_quantity_liters = fields.Float(string='Fuel Consumed (L)', readonly=True)

    def init(self) -> None:
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH dpr_summary AS (
                    SELECT dpr.project_id, dpr.report_date AS date, dpr.company_id, COUNT(dpr.id) AS dpr_count
                    FROM project_daily_report dpr
                    GROUP BY dpr.project_id, dpr.report_date, dpr.company_id
                ),
                equipment_summary AS (
                    SELECT project_id, date, SUM(liters) AS fuel_quantity_liters
                    FROM construction_equipment_fuel_log
                    GROUP BY project_id, date
                ),
                all_keys AS (
                    SELECT project_id, date, company_id FROM dpr_summary
                    UNION
                    SELECT project_id, date, NULL::integer AS company_id FROM equipment_summary
                )
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    k.project_id,
                    COALESCE(k.company_id, p.company_id) AS company_id,
                    k.date,
                    COALESCE(ds.dpr_count, 0) AS dpr_count,
                    COALESCE(es.fuel_quantity_liters, 0) AS fuel_quantity_liters
                FROM all_keys k
                JOIN construction_project p ON k.project_id = p.id
                LEFT JOIN dpr_summary ds ON k.project_id = ds.project_id AND k.date = ds.date
                LEFT JOIN equipment_summary es ON k.project_id = es.project_id AND k.date = es.date
                WHERE k.date IS NOT NULL
            )
        """)
```

### 2. Mandatory `flush_all()` Before Querying SQL Views

In unit tests or services querying `_auto = False` views, always flush the cache before reading:

```python
# Create test data
dpr = self.env['project.daily.report'].create({...})

# FLUSH ORM CACHE TO DATABASE ENGINE
self.env.flush_all()

# Query SQL analytical cube
dashboard_records = self.env['construction.site.operations.dashboard'].search([
    ('project_id', '=', self.project.id),
    ('date', '=', '2025-06-15'),
])
self.assertEqual(dashboard_records[0].labor_hours, 120.0)
```

### 3. Accurate `_render_qweb_pdf` Invocations

Always pass the report reference explicitly as the first argument, and records as `res_ids`:

```python
rep_dpr = self.env.ref('construction_site_reports.action_report_daily_site')

# Correct invocation:
pdf_content, report_type = rep_dpr._render_qweb_pdf(rep_dpr, res_ids=dpr.ids)
# OR using XML ID string:
pdf_content, report_type = self.env['ir.actions.report']._render_qweb_pdf(
    'construction_site_reports.action_report_daily_site',
    res_ids=dpr.ids
)
```

---

## ⚠️ Pitfalls

1. **Underlying Table vs Model Name Confusion in Raw SQL:**
   Remember that model names with dots translate to underscores in SQL tables (e.g. `construction.concrete.cube` becomes table `construction_concrete_cube`, NOT `construction_concrete_cube_test`). Always verify table name via `self.env['model.name']._table`.
2. **PostgreSQL NULL Type Resolution in UNION Queries:**
   In PostgreSQL CTE unions, `SELECT project_id, date, NULL FROM ...` can cause `UNION types "integer" and "text" cannot be matched` if another query selects an integer. Always explicitly typecast: `NULL::integer AS company_id`.
3. **QWeb PDF wkhtmltopdf Test Environments:**
   In test environments without running network workers, Odoo's `_render_qweb_pdf` falls back to `_render_qweb_html` automatically unless `force_report_rendering` is set. Validating byte length (`len(content) > 100`) ensures proper template evaluation without crashing.

---

## Verification

Run test suite and verify 0 failures and 0 errors:

```bash
/Users/gamal/odoo/odoo18.0/odoo-bin --test-enable --test-tags=construction_site_reports \
  -c /Users/gamal/odoo/odoo18.0/odoo18_dev.conf -d odoo18_construction --stop-after-init
```
Result:
```
INFO odoo18_construction odoo.tests.result: 0 failed, 0 error(s) of 2 tests when loading database 'odoo18_construction'
```

---

## References

- Related file: `orm/modular-daily-report-aggregation-hooks-and-inconsistent-store.md`
- Related file: `orm/construction-cross-module-backcharge-and-equipment-fuel-tracking.md`
