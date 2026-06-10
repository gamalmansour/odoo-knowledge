# Portal Workflow Rule Bypassing for Supervisors/Viewers
**Category:** Portal/Views  
**Odoo Versions:** 17, 18, 19  
**Tags:** `portal`, `controller`, `workflow`, `redirect`, `supervisor`

## 📝 Problem
In portal controllers, workflow enforcement rules (e.g., sequence validation, blocking visits out of order) are often applied generically. This causes an issue where **Supervisors or Viewers** clicking on a record to review it are unexpectedly blocked or redirected (e.g., to the calendar view) because the system applies the workflow rule to them, even though they are not the owner/actor of the document.

## ✅ Solution
When applying document-level workflow rules (like sequence enforcement) in a portal controller route, always ensure the condition explicitly checks if the current user is the actual actor (e.g., the salesperson) before enforcing the block.

### Before:
```python
enforce_sequence = getattr(user.company_id, 'enforce_visit_sequence', True)
if enforce_sequence and self._get_blocking_predecessor_visit(visit):
    # This inadvertently blocks supervisors trying to review the visit!
    return request.redirect('/my/visits?blocked_visit=1')
```

### After:
```python
enforce_sequence = getattr(user.company_id, 'enforce_visit_sequence', True)
# Only block if the current user is the assigned salesperson
is_own_visit = visit.salesperson_id.id == user.id

if is_own_visit and enforce_sequence and self._get_blocking_predecessor_visit(visit):
    return request.redirect('/my/visits?blocked_visit=1')
```

## ⚠️ Pitfalls
- **Missing the `is_own_visit` check:** Assuming that anyone accessing the detail page via `/my/model/<id>` route is the document owner. In standard Odoo, supervisors or managers may have access to their subordinates' portal documents and should bypass ownership-specific workflow blocks.
