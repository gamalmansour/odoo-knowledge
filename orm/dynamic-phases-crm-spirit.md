# Dynamic Phases Workflow Pattern (CRM Spirit)

**Severity:** 🟡 Medium

**Category:** ORM / Workflow
**Tags:** #crm, #workflow, #phases, #architecture
**Odoo Versions:** V15, V16, V17, V18, V19
**Last Verified:** 2026-05-25

## Problem
Hardcoding phases or stages using a `Selection` field causes "spaghetti code" where business rules, UI visibility, and readonly locks are spread across multiple Python compute methods and XML views. Every new phase or rule change requires a codebase update.

## Solution ✅
Follow the "CRM Spirit" by converting the static selection field into a dynamic database model (e.g., `o2c.phase` or `my_app.stage`).

### Key Elements:
1. **Configuration Model (`my_app.stage`)**:
   - Create fields for UI visibility (`show_budget`, `show_delivery_notes`).
   - Create fields for readonly locks (`lock_header`, `lock_financials`).
   - Create fields for entry requirements (`require_cost_center`, `require_pm`).
2. **Main Model Compute Methods**:
   - Add compute methods on the main model that read the current stage's configuration flags and set corresponding boolean fields (e.g., `is_budget_shown = any(p.show_budget for p in prev_phases)`).
   - Use these boolean fields in the XML views with `invisible="not is_budget_shown"` and `readonly="is_budget_locked"`.
3. **Centralized Validation (`write` override)**:
   - Override the `write` method to intercept changes to `stage_id`.
   - Validate transition requirements dynamically by reading the target stage's requirement flags.

## ⚠️ Pitfalls
- **Reinventing the Wheel:** Before creating a custom model like `o2c.phase`, check if Odoo already provides a native phase/stage model for the parent object (e.g., `project.project.stage` or `crm.stage`). It is ALWAYS better to `_inherit` the native stage model and add your custom CRM Spirit flags to it. This keeps the system aligned with standard Odoo views, menus, and groupings.
- **Data Loss on Migration:** Changing an existing `Selection` field to a `Many2one` field will drop the data for all existing records. If migrating a live system, you MUST write a data migration script (or pre-seed the table via XML and map the old string values to the new IDs).
- **Visibility Inheritance:** In a linear workflow, a tab revealed in Phase 3 should usually stay visible in Phase 4. Use `any()` over all previous phases up to the current sequence, instead of just checking the current phase.

## Pre-mortem (6-Month Failure Simulation)
- **Bottleneck:** The system becomes slow because compute methods run heavy DB queries on every form load.
- **Safeguard:** Use `@api.depends('stage_id')` correctly and leverage Odoo's ORM cache. Pre-seeding phases ensures there's only a handful of records to read.

## Reference
- `zakham_crm_lead_status` addon
- `project_o2c` phase implementation
