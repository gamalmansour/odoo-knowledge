# Odoo 19 QWeb `%%` XML Unescaping Crash, `at_install` JSONB Partner Test Trap & KPI/TM/Stock Hardening

| Field | Value |
|---|---|
| **Category** | views |
| **Odoo Versions** | 18, 19 |
| **Severity** | 🔴 Critical |
| **Last Verified** | 2026-11-22 |
| **Tags** | `qweb`, `xml-convert`, `percentage`, `post_install`, `jsonb`, `kpi`, `trade-marketing`, `analytic_distribution` |
| **Author** | ENG/Gamal Mansour |

## Problem / Overview

During Odoo 19 remediation and Playwright E2E testing across KPI (`ss_kpi`), Trade Marketing (`ss_trade_marketing*`), Secondary UoM (`product_secondary_uom`), Warehouse Split, and Journal Entry PDF printing (`oc_print_journal_entries`), four subtle Odoo 19 pitfalls surfaced:

1. **QWeb `%%` Escaping Inside XML Templates Causes `ValueError: incomplete format`:**
   Writing `<span t-out="'%.2f%%' % (val or 0.0)"/>` inside an Odoo XML `<template>` gets unescaped by Odoo's XML loader (`odoo/tools/convert.py`) into `'%.2f%'` (a single `%`) in `ir.ui.view.arch_db`. Rendering the HTML/PDF report then crashes with `HTTP 500 — ValueError: incomplete format`.
2. **`@tagged('post_install', '-at_install')` Required When Any Installed Module Marks `res.partner.name` as `translate=True`:**
   On databases where a sibling addon (e.g. `customer_level_chart`) alters `res_partner.name` to JSONB (`translate=True`), unit tests in modules that load *before* that addon at `at_install` time fail with `psycopg2.errors.InvalidTextRepresentation: invalid input syntax for type json` when creating a `res.partner`.
3. **Analytic Distribution Multi-Plan Keys (`"id1,id2": pct`) in QWeb Reports:**
   In Odoo 17–19, `account.move.line.analytic_distribution` keys can be comma-separated account IDs (`"12,45": 100.0`). Looking up `line.analytic_distribution.get(dist)` after splitting `distribution.split(',')` always returns `None` and triggers N+1 ORM lookups + potential `AccessError`/`MissingError`.
4. **Silent `AccessError` Swallowing in Cross-Module Computed KPI Bridges:**
   Wrapping `_kpi_compute_source()` in `except Exception: return 0.0` hides `AccessError` when an HR evaluator lacks Sales/Visit/Trade Marketing read rights, silently reporting `0.0%` performance for high-performing reps.

## Solution ✅

### 1. Put Literal `%` Outside the Format String in QWeb XML
```xml
<!-- ✅ CORRECT — immune to Odoo XML %% unescaping -->
<span t-out="'%.2f' % (line.score_pct or 0.0)"/>%
```

### 2. Multi-Plan Analytic Distribution in QWeb (Safe & Batch)
```xml
<t t-if="line.analytic_distribution">
    <t t-foreach="line.analytic_distribution.items()" t-as="dist_item">
        <t t-set="acc_ids" t-value="[int(x) for x in str(dist_item[0]).split(',') if x.strip().isdigit()]"/>
        <t t-set="accs" t-value="line.env['account.analytic.account'].sudo().browse(acc_ids).exists()"/>
        <div t-if="accs">
            <span t-out="' / '.join(accs.mapped('display_name'))"/>:
            <span t-out="'%.2f' % (dist_item[1] or 0.0)"/>%
        </div>
    </t>
</t>
```

### 3. Tag Cross-Module Tests as `post_install` on JSONB Partner Databases
```python
from odoo.tests.common import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestTmKpi(TransactionCase):
    ...
```

### 4. Company-Scoped `sudo()` Inside Cross-Module KPI & Visit Bridges
Instead of swallowing `AccessError` to `0.0`, read operational models (`sale.visit`, `sale.target`, `salesperson.commission`, `ss.tm.compliance`) with explicit `('company_id', '=', company.id)` domain + `.sudo()`, and always check `if existing.filtered(lambda c: c.visit_id == visit): continue` *before* claiming unlinked scheduled checkpoints (ordered `date asc, period_index asc, id asc`) for true idempotency.

## ⚠️ Pitfalls

- **Inherited NULL line dates in SQL filters:** Filtering child contract lines with `('date_from', '<=', target_date)` in SQL silently drops every line whose `date_from`/`date_to` is `NULL` (inherited from its parent contract). Fetch active/running parent contracts first and evaluate `(line.date_from or contract.date_from)` in Python.
- **QWeb `t-lang="o.partner_id.lang"` on Journal Entries:** Miscellaneous journal entries have `partner_id = False`, producing `t-lang="False"` and breaking Arabic RTL rendering. Always use `t-lang="o.partner_id.lang or env.lang"`.
- **Odoo 19 `Product Unit` Decimal Precision:** Replace deprecated `digits='Product Unit of Measure'` with `digits='Product Unit'`, and guard secondary UoM computations so products without `secondary_uom_id` display `0.0` (never raw base pieces).
- **Guard `res.users.allowed_picking_type_ids`:** Restrict the field with `groups='base.group_system'`, exempt `user.id in (1, 2)` (`OdooBot` & `base.user_admin`), scope by `company_id`, and clear cache on `stock.picking.type` archive/unlink.
