# Subcontractor BOQ Scope Filtering, 4-Field Cascade (`boq_item_id`, `name`, `owner_boq_line_id`, `cost_code_id`), and Upstream Comodel Stub Registration

## 📋 Metadata

| Field | Value |
|---|---|
| **Category** | `Best Practices` |
| **Severity** | 🔴 Critical |
| **Odoo Versions** | 16, 17, 18, 19 |
| **Tags** | `construction`, `subcontractor`, `boq`, `cost-code`, `cbs`, `onchange`, `domain`, `hierarchy`, `unknown-comodel` |
| **Author** | ENG/Gamal Mansour |
| **Last Verified** | 2026-10-15 |

---

## 🚨 Problem Statement

In Construction ERP Subcontracts (`contract.subcontractor` / `contract.subcontractor.line`), three interconnected issues caused confusion and data entry friction in the **BOQ Lines** tab:

1. **Unfiltered / Over-Broad BOQ Dropdowns:**
   - `owner_boq_line_id` (`contract.boq.line`) had no domain restriction at all, displaying all BOQ lines across all contracts (including section headers and direct-execution items).
   - `boq_item_id` (`project.boq.item`) used a loose `OR` domain `['|', ('execution_method', '=', 'subcontract'), ('breakdown_type', '=', 'subcontractor')]`. When a Level 1 root BOQ item had `execution_method = 'subcontract'`, its child breakdown lines (`MAT-*` Material, `EQ-*` Equipment, `LAB-*` Labor) inherited `execution_method = 'subcontract'` and polluted the subcontractor BOQ dropdown.
2. **Disconnected 4 Core Fields (`boq_item_id`, `name`, `owner_boq_line_id`, `cost_code_id`):**
   - `boq_item_id` is often a Level 2 or Level 3 breakdown sub-item (`breakdown_type == 'subcontractor'`), whereas `contract_boq_line_id` is stored on the Level 1 root `project.boq.item`. Checking `boq_item_id.contract_boq_line_id` directly without walking up `parent_id` meant `owner_boq_line_id` stayed empty for Level 2/3 subcontractor items.
   - `cost_code_id` was missing on `contract.boq.line` and `project.boq.item`, so selecting a BOQ item never populated the CBS Cost Code on the subcontract line.
   - `owner_boq_line_id` was placed as the 1st column instead of `boq_item_id` (the primary operational field), and `name` only auto-filled when blank rather than updating when `boq_item_id` changed.
3. **`_unknown` Comodel Trap Across Upstream/Downstream Modules:**
   - Because `construction_costcode` depends on `construction_project` (which depends on `construction_contract`), defining `Many2one('construction.cost.code')` in `construction_contract` or `construction_project` caused Odoo's `Many2one.setup_nonrelated()` to overwrite `field.comodel_name = '_unknown'` during intermediate `registry.setup_models()` calls before `construction_costcode` loaded, causing `rec.cost_code_id` to return `_unknown(id,)` instead of `construction.cost.code(id,)`.

---

## ✅ Solution

### 1. Strict Subcontract Scope Domains on Both BOQ Dropdowns

- **`project.boq.item` (`boq_item_id`)**: Restrict to root items (`parent_id == False`) with `execution_method == 'subcontract'`, OR breakdown sub-items explicitly typed as `breakdown_type == 'subcontractor'`:
  ```python
  domain="[('project_id', '=', parent.project_id), ('display_type', '=', False), ('is_section', '=', False), '|', '&', ('parent_id', '=', False), ('execution_method', '=', 'subcontract'), ('breakdown_type', '=', 'subcontractor')]"
  ```
- **`contract.boq.line` (`owner_boq_line_id`)**: Add stored computed boolean `has_subcontract_scope` on `contract.boq.line` (checking `boq_type == 'subcontractor'`, `breakdown_ids.cost_type == 'subcontractor'`, or linked `project_boq_item_ids` and their `child_ids`), and filter `owner_boq_line_id` by:
  ```python
  domain="[('contract_id', '=', parent.owner_contract_id), ('display_type', '=', False), ('is_section', '=', False), ('has_subcontract_scope', '=', True)]"
  ```

### 2. Hierarchy Helpers & 4-Field Auto-Cascade (`boq_item_id` $\rightarrow$ `name`, `owner_boq_line_id`, `cost_code_id`)

- Place `boq_item_id` as the **first column** in `contract.subcontractor` BOQ Lines.
- Add `_get_root_contract_boq_line()` and `_get_effective_cost_code()` on `project.boq.item` to walk up `parent_id` when `boq_item_id` is a Level 2/3 breakdown item.
- In `_onchange_boq_item_id()`, `create()`, and `write()` on `contract.subcontractor.line`, automatically populate:
  1. `name` (from `boq_item_id.name`)
  2. `owner_boq_line_id` (via `boq_item_id._get_root_contract_boq_line()`)
  3. `cost_code_id` (via `boq_item_id._get_effective_cost_code()`)
  4. `wbs_id`, `uom_id`, `qty`, and `unit_price`.

### 3. Upstream Base Stub for `construction.cost.code`

- Define a lightweight base stub `class ConstructionCostCode(models.Model): _name = 'construction.cost.code'` in `construction_contract`, and extend it with `_name = 'construction.cost.code'` + `_inherit = 'construction.cost.code'` in `construction_costcode`. This guarantees `'construction.cost.code' in model.pool` is always `True` when `construction_contract` and `construction_project` run `setup_models()`.

---

## ⚠️ Pitfalls to Avoid

- **Never use `('execution_method', '=', 'subcontract')` without `('parent_id', '=', False)`** when filtering `project.boq.item` for subcontractors, because child material/labor/equipment breakdown items under a root subcontracted item may carry `execution_method = 'subcontract'`.
- **Never check `boq_item.contract_boq_line_id` only at the leaf level** — always walk up `parent_id` so Level 2 and Level 3 breakdown items resolve their root Owner Contract BOQ Line and CBS Cost Code.
- **Never reference a downstream module's model in `Many2one` without a base stub in the upstream module**, or Odoo will permanently mutate `field.comodel_name = '_unknown'` during partial module upgrades (`-u`).
