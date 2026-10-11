# Odoo 19: Cannot convert non-stored field to SQL because it is not stored

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-09-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo-19`, `orm`, `domain`, `non-stored`, `compute`, `sale_order_count`, `search_read`

---

## Problem

When opening a menu or view whose `ir.actions.act_window` domain (or a `<filter>` domain in a search view, or `default_order` in a `<list>` view) targets a non-stored computed field, the RPC call `web_search_read` crashes with:

```text
ValueError: Cannot convert res.partner.total_real_discount to SQL because it is not stored
  File "odoo/addons/web/models/models.py", line 67, in web_search_read
    records = self.search_fetch(domain, specification.keys(), offset=offset, limit=limit, order=order)
  File "odoo/orm/models.py", line 5385, in _search
    query.order = self._order_to_sql(order, query)
  File "odoo/orm/models.py", line 5256, in _order_to_sql
    term = self._order_field_to_sql(alias, field_name, sql_direction, sql_nulls, query)
  File "odoo/orm/fields.py", line 1216, in to_sql
    raise ValueError(f"Cannot convert {self} to SQL because it is not stored")
```

## Root Cause

In Odoo 19, the ORM translates both filtering conditions (`Domain._to_sql()`) AND ordering clauses (`_order_to_sql()`) directly to SQL via `field.to_sql()`.

If a field is computed without `store=True`:
1. **In Domains:** The leaf condition cannot be evaluated in SQL unless a custom `search='_search_<fname>'` routine exists.
2. **In Orders / Sorting:** An un-stored computed field **CANNOT** be used in `_order`, `default_order="..."` on `<list>`/`<tree>`, or as an SQL `ORDER BY` clause, because the column does not physically exist in PostgreSQL.

Common triggers:
- Setting `default_order="my_computed_field desc"` on a `<list>` / `<tree>` view when `my_computed_field` has `store=False`.
- Setting `domain="[('sale_order_count', '>', 0)]"` where `sale_order_count` is standard Odoo's un-stored compute field.

## Solution ✅

Replace the un-stored computed field filter with a direct relational domain on the underlying One2many / Many2one relation:

**Wrong ❌:**
```xml
<field name="domain">['|', ('customer_rank', '>', 0), ('sale_order_count', '>', 0)]</field>
```

**Correct ✅:**
```xml
<field name="domain">['|', ('customer_rank', '>', 0), ('sale_order_ids.state', 'in', ['sale', 'done'])]</field>
```

Alternatively, if filtering on a custom model field, either:
1. Store the computed field: `store=True` (with appropriate `@api.depends`), or
2. Add a `search='_search_field_name'` method on the model to resolve the domain to a SQL-compatible condition.

After modifying the XML, upgrade the module to update the `ir.actions.act_window` record in the database:
```bash
odoo-bin -c custom.conf -d <dbname> -u <module_name> --stop-after-init
```

## ⚠️ Pitfalls

- Editing the XML file on disk does **NOT** update the existing `ir.actions.act_window` or `ir.ui.view` record in PostgreSQL! You must run `-u <module_name>`.
- Client browsers cache OWL action definitions in memory. After upgrading, users must do a **Hard Refresh** (`Ctrl + F5` or `Cmd + Shift + R`) to pull the updated domain from the server.

## Verification

Test the domain directly via Python shell or JSON-RPC to confirm it translates to SQL cleanly:

```python
domain = ['|', ('customer_rank', '>', 0), ('sale_order_ids.state', 'in', ['sale', 'done'])]
env['res.partner'].web_search_read(domain=domain, specification={'display_name': {}}, limit=5)
```

## References

- Related file: `views/odoo-19-search-view-group-attributes-deprecated.md`
