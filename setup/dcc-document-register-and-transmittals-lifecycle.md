# Document Register & Transmittal Lifecycle: Frozen Snapshots, Concurrency Counter Lock, and Superuser Transition Bypass

**Category:** Setup / Construction DCC  
**Severity:** 🔴 Critical  
**Odoo Versions:** 16, 17, 18, 19  
**Tags:** `setup`, `dcc`, `document-register`, `transmittal`, `concurrency`, `counter-lock`, `frozen-snapshot`, `superuser-bypass`, `smart-button`  
**Last Verified:** 2026-10-04  

---

## Problem Description ❌

In custom Document Control (DCC) suites for construction projects, users accessing the **Document Register** (`dcc.document`) and **Transmittals** (`dcc.transmittal`) screens frequently encounter:
1. **Completely Empty Screens:** Newly installed or clean databases have 0 records because standard demo data often references nonexistent generic projects (`project.project`) rather than vertical construction projects (`construction.project`).
2. **Missing In-Flight Revision Snapshot on Transmittal Lines:** In web client form views, selecting a document in a transmittal line left the `revision_code` blank until record creation because the logic only executed inside `create()`.
3. **Deadlock in State Transitions for Administrative Scripts:** `action_issue`, `action_reset_to_draft`, and `action_void` enforced strict `has_group()` checks without allowing `is_superuser()`, failing with `UserError` when invoked by administrative deployment scripts or system automation.
4. **Lack of Bi-Directional Traceability:** Document controllers could not view transmittal history directly from the document form, and transmittal managers could not see document counts in list views.

---

## Symptoms / Error Messages

- **Empty Views:** "No records found" in Document Register (`action_dcc_document`) and Transmittals (`action_dcc_transmittal`).
- **UI Lag / Blank Field:** Selecting a document on a transmittal line does not auto-populate `revision_code` in the web client until save.
- **Permission UserError:** `UserError: Only Document Controllers and Managers can issue transmittals.` or `Only Document Managers can reset a transmittal.` when invoked by scripts running under `SUPERUSER_ID`.
- **Concurrency Collision:** High-volume transmittals generated in parallel can create duplicate sequence numbers if sequential counters do not use row-level locking (`SELECT ... FOR UPDATE`).

---

## Root Cause Analysis 🔍

1. **Decoupled Architecture between Demo & Vertical Models:** DCC depends on `dcc.project.mixin`, which points to `construction.project`. Initializing databases without demo data leaves both document registers and transmittal cover notes empty.
2. **Missing Web Client Onchange for Frozen Snapshot:** DCC transmittal lines intentionally store `revision_code` as an independent frozen Char field (not a Related field) to preserve historical contract accuracy. However, without `@api.onchange('document_id')`, the web client fails to pre-fill the current revision code during interactive entry.
3. **Missing `is_superuser()` Check:** Python methods checked `if not self.env.user.has_group('...'): raise UserError(...)`. In Odoo 18, the `SUPERUSER_ID` (Administrator) might not have explicit custom group memberships unless assigned or checked via `self.env.is_superuser()`.

---

## Solution ✅

### 1. Transmittal Line Onchange for Interactive Revision Capture

In `dcc.transmittal.line`, implement an onchange handler to populate `revision_code` immediately when a document is selected:

```python
@api.onchange('document_id')
def _onchange_document_id(self):
    if self.document_id and self.document_id.current_revision_code:
        self.revision_code = self.document_id.current_revision_code
```

### 2. Permit Superuser Bypass on Lifecycle Actions

Update permission guards across `dcc.document` and `dcc.transmittal`:

```python
# In dcc_document.py
def action_void(self):
    if not (self.env.is_superuser() or self.env.user.has_group('construction_dcc.group_dcc_controller')):
        raise UserError(_('Only Document Controllers and Managers can void a document.'))
    # ...

# In dcc_transmittal.py
def action_issue(self):
    if not (self.env.is_superuser() or self.env.user.has_group('construction_dcc.group_dcc_controller')):
        raise UserError(_('Only Document Controllers and Managers can issue transmittals.'))
    # ...

def action_reset_to_draft(self):
    if not (self.env.is_superuser() or self.env.user.has_group('construction_dcc.group_dcc_manager')):
        raise UserError(_('Only Document Managers can reset a transmittal.'))
    # ...
```

### 3. Bi-Directional Navigation & Computed Counters

Add reverse relations and stat counters:

```python
# In dcc.document:
transmittal_line_ids = fields.One2many(
    'dcc.transmittal.line',
    'document_id',
    string='Transmittal Lines'
)
transmittal_count = fields.Integer(
    string='Transmittals Count',
    compute='_compute_transmittal_count',
    store=True
)

@api.depends('transmittal_line_ids')
def _compute_transmittal_count(self) -> None:
    for doc in self:
        doc.transmittal_count = len(doc.transmittal_line_ids)

def action_view_transmittals(self):
    self.ensure_one()
    transmittal_ids = self.transmittal_line_ids.mapped('transmittal_id').ids
    return {
        'name': _('Transmittals'),
        'type': 'ir.actions.act_window',
        'res_model': 'dcc.transmittal',
        'view_mode': 'list,form',
        'domain': [('id', 'in', transmittal_ids)],
        'context': {'default_project_id': self.project_id.id},
    }
```

```python
# In dcc.transmittal:
document_count = fields.Integer(
    string='Documents Count',
    compute='_compute_document_count',
    store=True
)

@api.depends('line_ids')
def _compute_document_count(self) -> None:
    for rec in self:
        rec.document_count = len(rec.line_ids)
```

### 4. UI Ribbons & Tree Summaries

Add visual state ribbons to both views:
- Document form: Ribbons for `Active` (green), `Superseded` (orange), `Void` (danger).
- Transmittal form: Ribbons for `Issued` (primary), `Acknowledged` (success).
- Transmittal list view: Display `document_count` column.
- Document list view: Display `transmittal_count` column.

---

## ⚠️ Pitfalls

1. **Do NOT Use Related Field for Revision Code on Transmittal Lines:**
   If `revision_code = fields.Char(related='document_id.current_revision_code')`, sending Rev 00 in January and revising the document to Rev 01 in March will **retroactively alter the January transmittal**. It must remain a stored snapshot Char populated at issue time.
2. **Sequential Numbering Locking:**
   Always use row-level locking (`SELECT ... FOR UPDATE` via `dcc.numbering.counter`) to prevent sequence collisions when multiple engineers issue transmittals or upload drawing batches concurrently.
3. **Avoid Deleting Issued Transmittals:**
   Transmittal lines must be strictly immutable once issued (`state != 'draft'`), and documents referenced in un-closed transmittals cannot be voided without throwing `UserError`.

---

## Verification Checklist

- [x] Document Register displays drawings, calculations, specifications, and reports across disciplines (ARCH, CIV, STR, MEC, ELE, HVAC).
- [x] Selecting a document in transmittal lines automatically populates `revision_code`.
- [x] Transmittal Smart Stat button navigates accurately to associated transmittals.
- [x] Superuser bypass allows administrative scripts and scheduled actions to transition records without ACL errors.
- [x] List views show `transmittal_count` and `document_count` without N+1 query bottlenecks (`store=True`).
