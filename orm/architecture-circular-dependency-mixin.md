# Architecture: Circular Dependencies with Base Mixins

**Date:** 2026-06-14
**Author:** ENG/Gamal Mansour
**Tags:** `#architecture`, `#dependencies`, `#mixin`, `#best-practices`
**Odoo Versions:** `V15+`
**Last Verified:** 2026-06-14

## Context
When building a reusable engine (e.g., `approval.mixin`) inside a base module (`construction_approvals`), and you need a context-specific field (e.g., `project_id`), adding that field directly in the base module forces the base module to depend on the upper-level module (`construction_project`).

## Problem / Error
```python
TypeError: Model 'contract.owner' inherits from non-existing model 'approval.mixin'.
```
This occurs because:
1. `construction_approvals` depends on `construction_project` (to get the `project_id` field).
2. `construction_project` depends on `construction_contract`.
3. `construction_contract` tries to inherit `approval.mixin` (from `construction_approvals`).
The registry fails because the modules form a circular dependency, leading to the base module being loaded *after* the module that needs its mixin.

## Solution ✅
Keep the base module pure and inject context from upper modules:

1. **Pure Base Module:** Remove any dependency on upper-level modules. The base module should only depend on `base` (and maybe `mail`).
   ```python
   # construction_approvals/__manifest__.py
   'depends': ['base', 'mail']
   ```
2. **Remove specific fields from base:** Do not define `project_id` in `approval.chain` inside the base module.
3. **Inject from Top Module:** In the upper-level module (`construction_project`), inherit the base model (`approval.chain`) and add the specific field.
   ```python
   # construction_project/models/approval_chain_ext.py
   class ApprovalChain(models.Model):
       _inherit = 'approval.chain'
       project_id = fields.Many2one('construction.project', string='Project')
   ```
4. **Update Views via XPath:** Inject the field into the UI from the upper module.

## ⚠️ Pitfalls
- **`ondelete='restrict'` on `ir.model`:** Avoid using `ondelete='restrict'` for `Many2one` fields pointing to `ir.model`. It will raise a `ValueError` during loading. Always use `ondelete='cascade'` for `ir.model` references.
- **Menu Hierarchy:** Do not set a `parent` menu ID pointing to an upper-level module inside the base module. Either make it a top-level menu or reparent it via `<record>` in the upper module.
