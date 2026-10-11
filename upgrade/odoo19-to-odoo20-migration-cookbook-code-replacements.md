# Odoo 19 to Odoo 20 Migration Cookbook: Code Replacements & Breaking Changes Reference

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 19, 20                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-08                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo20`, `upgrade`, `migration`, `cookbook`, `code-replacements`, `ir.access.csv`, `owl3`, `constraints`, `accounting`, `inventory`, `hr`

---

## Overview

Based on official Odoo 20.0 Community and Enterprise source trees and the *Odoo Migration Cookbook (v19 to v20)* by Probuse Consulting, this reference provides exact code replacements for migrating custom modules, views, controllers, security, and models from Odoo 19.0 to Odoo 20.0.

---

## 1. Security & Access Rules Revolution

### 🔴 XML `<record model="ir.rule">` and `ir.model.access.csv` are REMOVED!
- Attempting to load XML `<record model="ir.rule">` raises a fatal `KeyError: 'ir.rule'`.
- Odoo 20 unifies model access rights and record rules into a single file: **`security/ir.access.csv`**.

#### Odoo 19 (Two files)
`ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_my_lock,lock,model_my_lock,base.group_user,1,1,1,0
```
Plus separate XML `ir.rule` records.

#### Odoo 20 — `security/ir.access.csv` (Unified)
```csv
id,name,model_id,group_id/id,operation,domain
access_my_lock,my.lock,my.lock,base.group_user,cru,
```

#### Syntax Rules for `ir.access.csv`:
| Column | Rule in Odoo 20 |
|---|---|
| `model_id` | **Technical model name** directly (e.g., `sale.order` or `my.lock`). NOT `model_sale_order` or `module.model_x`. |
| `group_id/id` | Group XML ID. Leave **empty** for global rules. |
| `operation` | Combination of letters: `crud`, `cru`, `cr`, `r`, `w`, `u`, `d`. (No separate boolean columns). |
| `domain` | Python domain string (record rule). Leave **empty** for full model access. |

⚠️ **Domain Pitfalls:**
- `[(1, '=', 1)]` and `[('1', '=', 1)]` fail validation. Use an empty domain string `,` for unconditional access.
- Domains referencing non-stored fields raise: `Field has no SQL representation`.
- Multi-company domain syntax:
  ```python
  # Odoo 20:
  ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
  ```
- Any custom `res.groups` XML file must be listed in `__manifest__.py` **before** `ir.access.csv`.

---

## 2. ORM & Python API Replacements

| Pattern / Feature | Odoo 19 | Odoo 20 Replacement |
|---|---|---|
| SQL Constraints | `_sql_constraints = [('name', 'sql', 'msg')]` | `_name = models.Constraint('sql', 'msg')` |
| View Architecture | `self.fields_view_get(...)` | `self._get_view(...)` |
| Access Check (Raise) | `self.check_access_rights('read')` | `self.check_access('read')` |
| Access Check (Boolean) | `self.check_access_rights('read', raise_exception=False)` | `self.has_access('read')` |
| User Group Check | `self.user_has_groups('group_xml_id')` | `self.env.user.has_groups('group_xml_id')` |
| Context Access | `self._context` | `self.env.context` |
| Active Company | `self.env.user.company_id` | `self.env.company` |
| System Parameters | `ir.config_parameter.get_param('key')` | `get_int / get_str / get_bool / set_str / set_bool / set_float` |
| Timezone Handling | `import pytz; pytz.timezone(...)` | `from datetime import UTC; from zoneinfo import ZoneInfo` |
| Archive Field Write | `record.write({'archive': True})` | `record.write({'active': False})` |
| Archive Action | Window action `toggle_active` | `action_archive` / `action_unarchive` |
| Mail Thread Mixin | `_inherit = ['mail.thread.cc']` | `_inherit = ['mail.thread']` (`mail.thread.cc` removed; MRO error if paired with `rating.mixin`) |
| Selection Add | `fields.Selection(selection_add=[...])` | MUST include `ondelete={'key': 'set default'}` |
| Inverse Sequence | Order dependent on definition | Use `write_sequence=10` on field definition |

### Constraints Example
```python
# Odoo 19
_sql_constraints = [
    ('code_uniq', 'unique(code, company_id)', 'Code must be unique per company.'),
]

# Odoo 20
_code_uniq = models.Constraint(
    'unique(code, company_id)',
    'Code must be unique per company.',
)
```

---

## 3. Search, Display Name & Domains

| Pattern | Odoo 19 | Odoo 20 Replacement |
|---|---|---|
| Name Search Override | `def _name_search(self, name, args, ...)` | `_rec_names_search = ('name', 'code')` and/or `_search_display_name` |
| Domain Expressions | `from odoo.osv import expression; expression.AND(...)` | `from odoo.fields import Domain; Domain.AND(...)` |
| Empty / False Domain | `from odoo.fields import FALSE_DOMAIN` | `Domain.FALSE` |
| Domain Operator `access` | *(Not available)* | `Domain('partner_id', 'access', 'write')`, `Domain('id', 'access', 'read')` |
| View Modifiers | `in 'x'` / `not in 'x'` | `== 'x'` / `!= 'x'` or tuple `in ('a', 'b')` |

---

## 4. Binary, Image, Excel, PDF & Time

### Binary Fields & Attachments
- In Odoo 20, reading a Binary field returns a `BinaryValue` (already raw bytes). Calling `base64.decodebytes(self.datas)` fails with `Incorrect padding` or double-decodes.
- Writing binary values:
  ```python
  from odoo.tools.binary import BinaryBytes
  record.datas = BinaryBytes(stream.getvalue(), filename=name)
  ```
- Images: `image_to_base64` is removed. Use `image_apply_opt(pil_image, 'PNG')` then `BinaryBytes(...)`.
- `ir.attachment`: Field is `raw` (bytes), not `datas`.
- QWeb Image URI:
  ```xml
  <!-- Odoo 20 -->
  <img t-att-src="image_data_uri(doc.image_1920) if doc.image_1920 else '/web/static/src/img/placeholder.png'"/>
  ```

### Excel & PDF
- `xlwt` is completely removed. Use `xlsxwriter` (with `{'in_memory': True}`) or `openpyxl`.
- `PyPDF2` imports changed to: `from odoo.tools.pdf import PdfFileWriter, PdfFileReader`.
- PDF Rendering engines split into:
  - `base_report_wkhtmltox` (wkhtmltopdf)
  - `base_report_paper_muncher` (in-house Paper Muncher renderer)

---

## 5. HTTP Controllers, RPC & Mail

| Pattern | Odoo 19 | Odoo 20 Replacement |
|---|---|---|
| Controller Route | `@http.route(..., type='json')` | `@http.route(..., type='jsonrpc')` |
| External JSON API | Custom / experimental | `/json/2/<model>/<method>` (JSON-2, `type='json2'`, Bearer auth) |
| Mail Tracking Values | Core `mail.tracking.value` | Addon `mail_tracking` (Discuss Tracking). Must depend on `mail_tracking` if reading history. |

---

## 6. SQL Reports

- `_table_query` attribute and method are REMOVED!
- In Odoo 20, override `_table_sql(self) -> SQL` returning `odoo.tools.SQL`:
```python
from odoo.tools import SQL

class SaleReport(models.Model):
    _inherit = 'sale.report'

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res['custom_field'] = SQL("s.custom_field")
        return res
```

---

## 7. Views, Kanban, and Icons

### Button Icons & Material Symbols
- Font Awesome icon classes (`fa fa-check`, `fa-trash`) on ViewButtons are REMOVED.
- Use standard icon names from `web/icons.py`:
  ```xml
  <!-- Odoo 20 -->
  <button icon="check" string="Confirm" class="btn-primary"/>
  <button icon="delete" string="Delete" class="btn-secondary"/>
  ```
- Permitted button icon names include: `check`, `save`, `close`, `history`, `edit_square`, `task`, `group`, `book`, `description`, `delete`, `settings`.

### Web Ribbon
```xml
<!-- Odoo 19 -->
<widget name="web_ribbon" text="Archived" bg_color="bg-danger"/>

<!-- Odoo 20 -->
<widget name="web_ribbon" title="Archived" bg_color="text-bg-danger" invisible="active"/>
```

### Kanban Template
- Template name changed to: `<t t-name="card">`.
- Project views inherit `project.view_project_card` and `project.view_task_card`.

### Form Views & Xpaths
- In `account.move` and `sale.order`, `product_id` and `name` are grouped inside `<column name="product_and_description">`. Direct xpath `/list/field[@name='product_id']` fails. Target direct list children or use hasclass.

---

## 8. Owl 3 (Frontend Web Client)

Odoo 20 web client is powered by **Owl 3**:
| Owl 2 (Odoo 17-19) | Owl 3 (Odoo 20) |
|---|---|
| `import { useState } from "@odoo/owl"` | `import { proxy } from "@odoo/owl"; this.state = proxy({ ... })` |
| `this.render()` | Removed. Updates to `proxy` or `signal` re-render automatically. |
| In template: `<t t-esc="state.foo"/>` | `<t t-out="this.state.foo"/>` (`this.` is mandatory) |
| Form inputs | `t-model` accepts a `signal` only. For proxy fields use: `t-att-value="this.state.x" t-on-input="onInput"` |
| Component Lifecycle | `onWillUpdateProps`, `onWillRender`, `onRendered` REMOVED. Use: `onWillStart`, `onMounted`, `onWillUnmount`, `onPatched`. |
| `t-portal` | Removed. Render into target DOM element directly or use standard portal helpers. |

---

## 9. Comprehensive Model Mapping Table

| Odoo 19 Model | Odoo 20 Replacement | Edition | Notes |
|---|---|---|---|
| `account.group` | `account.account (parent_id)` | CE + EE | `account.group` is DELETED. Hierarchy lives on parent accounts. |
| `account.asset` (state='model') | `account.depreciation.model` | EE | Asset templates decoupled from individual asset records. |
| `hr.contract` | `hr.version` | CE + EE | Contracts table and model renamed to version. |
| `hr.leave.type` | `hr.work.entry.type` | CE + EE | Time off types unified into work entry types (`count_as='absence'`). |
| `hr.expense.sheet` | `hr.expense` | CE + EE | Direct expense processing without intermediate sheet model. |
| `stock.scrap` | `stock.move (is_scrap=True)` | CE + EE | Scrap model replaced with boolean flag on standard stock move. |
| `stock.return.picking` | `stock.picking._create_return()` | CE + EE | Multi-step return wizard replaced with direct method. |
| `stock.quant.package` | `stock.package` | CE + EE | Model renamed. |
| `stock_picking_batch` | `stock` | CE + EE | Module merged into stock core. |
| `note.note` | `project.task (project_todo)` | CE + EE | Standalone notes unified with project todos. |
| `industry_fsm` | `project` | EE | Field service merged directly into project app. |
| `crossovered.budget` | `budget.analytic` | EE | Enterprise budget app models renamed. |
| `crossovered.budget.lines` | `budget.line` | EE | Lines renamed. |

---

## 10. Comprehensive Field Mapping Table

| Model | Odoo 19 Field | Odoo 20 Replacement | Notes |
|---|---|---|---|
| `sale.order` | `state == 'done'` | **REMOVED** | Valid states: `draft`, `sent`, `sale`, `cancel`. |
| `product.template` | `type == 'product'` | `is_storable` (Boolean) | `type` values are now `consu` / `service`. Storable is a boolean flag. |
| `purchase.order.line` | `product_uom_id` | `uom_id` | Renamed to match standard UoM field convention. |
| `res.partner` | `company_type` | `is_company` (Boolean) | `company_type` removed. |
| `res.partner` | `mobile` | `phone` | `mobile` removed; unified into phone. |
| `res.users` | `groups_id` | `group_ids` | Fixed naming inconsistency. |
| `project.task` | `user_id` | `user_ids` (M2M) | Tasks support multiple assignees natively. |
| `account.payment` | `state == 'in_process'` | `state == 'paid'` | Lifecycle renamed. |
| `account.payment` | `state == 'paid'` | `state == 'reconciled'` | Old 'paid' is now 'reconciled'. |
| `account.analytic.account`| `group_id` | `plan_id` | Tied to analytic plan. |
| `crm.lead` | `currency_id` | `company_currency` | Currency on leads. |
| `mrp.production` | `show_produce_all` | **REMOVED** | Single `button_mark_done`. |

---

## ⚠️ Checklist for 19 → 20 Migration

1. **Security:** Replace all `ir.model.access.csv` + XML `ir.rule` files with single `security/ir.access.csv`.
2. **Constraints:** Convert `_sql_constraints` lists to `models.Constraint` class attributes.
3. **Pytz:** Replace all `pytz` imports with `datetime.UTC` and `zoneinfo.ZoneInfo`.
4. **Context & Environment:** Replace `self._context` with `self.env.context` and `self.env.user.company_id` with `self.env.company`.
5. **Views:** Replace Font Awesome `fa-` button icons with Material Symbols / `web/icons.py` names.
6. **Owl:** Update frontend Owl components from `useState` to `proxy()` and update lifecycle hooks.
7. **Accounting:** Remove all references to `account.group` and update payment state domains (`in_process` -> `paid`, `paid` -> `reconciled`).
8. **Inventory & MRP:** Remove `stock.scrap` references and use `stock.move(is_scrap=True)`. Remove `flexible_consumption` and `show_produce_all`.
9. **HR:** Replace `hr.contract` with `hr.version` and `hr.leave.type` with `hr.work.entry.type`.

---

## References

- *Odoo Migration Cookbook: Version 19 to Version 20* (Probuse Consulting Service Pvt. Ltd., September 2026).
- Official Odoo 20.0 Community & Enterprise source trees (`odoo/`, `enterprise/`).
