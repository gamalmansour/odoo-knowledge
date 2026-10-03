# Critical Path Method (CPM) Network Dependency Integrity and Tracking Attribute Guard

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `project`, `schedule`, `cpm`, `kahn-algorithm`, `topological-sort`, `mail-thread`, `tracking`, `cycle-detection`

---

## Problem

When modeling project schedule networks (e.g. `project.schedule.phase` or WBS activities) with predecessor dependencies and Critical Path Method (CPM) forward/backward passes:
1. **Dependency Cycles / Infinite Loop**: If users establish cyclic dependencies (e.g. A depends on B, B depends on A), graph traversal algorithms freeze or raise recursion errors.
2. **Missing `mail.thread` for `tracking=True`**: Adding `tracking=True` to fields like `state`, `date_start`, or `date_end` on a model that does not inherit `mail.thread` triggers startup warnings:
```text
WARNING ? odoo.fields: Field project.schedule.phase.state: unknown parameter 'tracking'
```
3. **Empty Planning Schedule**: Auto-generated work orders from BOQ items fail to compute their target planned execution dates and fall back to the project start date because no schedule phases are linked.

## Root Cause

- Topological sorting algorithms (such as Kahn's algorithm) require Directed Acyclic Graphs (DAG). Without self-dependency and cross-project validation via `@api.constrains('depends_on_ids')`, invalid relationships enter the database before CPM executes.
- `tracking=True` is an Odoo Mail feature; defining it without inheriting `['mail.thread', 'mail.activity.mixin']` causes Odoo ORM to discard the attribute with a warning.

## Solution ✅

1. **Inherit `mail.thread` and `mail.activity.mixin`**:
```python
class ProjectSchedulePhase(models.Model):
    _name = 'project.schedule.phase'
    _description = 'Project Schedule Phase'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, date_start'

    name = fields.Char(string='Phase Name', required=True, tracking=True)
    date_start = fields.Date(string='Planned Start', required=True, tracking=True)
    date_end = fields.Date(string='Planned End', required=True, tracking=True)
    state = fields.Selection([...], tracking=True)
```

2. **Add Model-Level Constraint Against Self and Cross-Project Dependencies**:
```python
    @api.constrains('depends_on_ids')
    def _check_dependencies(self) -> None:
        for rec in self:
            if rec in rec.depends_on_ids:
                raise ValidationError(_("A schedule phase cannot depend on itself."))
            if any(dep.project_id != rec.project_id for dep in rec.depends_on_ids):
                raise ValidationError(_("All predecessor phases must belong to the same project."))
```

3. **Safe Topological Order with Kahn's Algorithm & CPM**:
```python
    def _run_cpm(self) -> None:
        phases = self.filtered(lambda p: p.date_start)
        if not phases:
            return

        ids = set(phases.ids)
        preds = {p.id: [d for d in p.depends_on_ids.ids if d in ids] for p in phases}
        succs = {p.id: [] for p in phases}
        for pid, plist in preds.items():
            for d in plist:
                succs[d].append(pid)
        dur = {p.id: max(p.duration or 0, 0) for p in phases}
        by_id = {p.id: p for p in phases}
        project_start = min(phases.mapped('date_start'))

        # Topological sort (Kahn)
        indeg = {pid: len(preds[pid]) for pid in preds}
        queue = [pid for pid in preds if indeg[pid] == 0]
        topo = []
        while queue:
            n = queue.pop(0)
            topo.append(n)
            for s in succs[n]:
                indeg[s] -= 1
                if indeg[s] == 0:
                    queue.append(s)
        if len(topo) != len(phases):
            raise UserError(_("The phase dependencies contain a cycle — cannot compute the critical path."))
```

## ⚠️ Pitfalls

- **Missing Import**: Ensure both `UserError` and `ValidationError` are imported from `odoo.exceptions`.
- **Search View Requirement**: Even operational secondary models like schedule phases should always have an explicit Search View with `Group By` filters (Project, Status, Date) so users can filter by project when navigating from the top-level menu.

## Verification

```bash
python odoo-bin -c odoo.conf -d <dbname> -u construction_project --test-enable --test-tags /construction_project:TestSchedulePhaseCPM --stop-after-init
```

## References

- Related file: `construction_project/models/project_schedule_phase.py`
- Related file: `construction_project/views/project_schedule_phase_views.xml`
- Fixed in: `construction_project` (18.0.1.33.0)
