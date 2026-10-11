# Import Hierarchical One2many Data

**Category:** Models
**Tags:** #one2many, #hierarchy, #boq, #import
**Last Verified:** 2026-07-02
**Odoo Versions:** 16, 17, 18, 19

## Problem
When linking two models (e.g., `construction.project` to `contract.owner`), copying a hierarchical one2many structure (like BOQ items with parent-child breakdowns) via an `onchange` method is error-prone and complex, due to handling `NewId` linking.

## Solution ✅
Instead of using `@api.onchange` to populate hierarchical data on a new record, provide an **"Import" button** in the view header.
This button triggers a Python action that iterates over the source's records and recursively creates the destination records.

```python
def action_import_boq_from_contract(self):
    self.ensure_one()
    if not self.contract_id:
        raise UserError(_("Please select an Owner Contract first."))
    if self.boq_item_ids:
        raise UserError(_("This project already has BOQ items. You cannot import again to avoid duplication."))
        
    for line in self.contract_id.boq_line_ids:
        boq_item = self.env['project.boq.item'].create({
            'project_id': self.id,
            # ... map fields ...
        })
        if not line.display_type and line.breakdown_ids:
            top_breakdowns = line.breakdown_ids.filtered(lambda b: not b.parent_id)
            self._import_boq_breakdown(top_breakdowns, boq_item)
    return True
```

## ⚠️ Pitfalls
- Doing this in `@api.onchange` requires manipulating dictionaries/tuples `(0, 0, {})` and dealing with `NewId` for parent-child relations which breaks easily.
- Always add a validation check (`if self.boq_item_ids: raise ...`) to prevent accidental duplication if the user clicks the button multiple times.
