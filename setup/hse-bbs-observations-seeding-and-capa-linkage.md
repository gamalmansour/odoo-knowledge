# HSE Behavior-Based Safety (BBS) Observations Empty Screen & CAPA Action Linkage

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `hse`, `safety`, `bbs`, `observations`, `capa`, `demo-data`, `mail.activity.mixin`

---

## Problem

When navigating to **Safety > Daily Operations > Observations (BBS)** (`action_hse_observation`), the list view renders completely empty:
1. No records appear in the table.
2. If safe acts were recorded, the default action context `{'search_default_unsafe': 1}` hid all `safe_act` records by default, misleading users into thinking their submissions were lost.
3. In `hse.observation`, when a safety officer clicks **Raise Action** (`action_raise_action`), a corrective action (`hse.action`) is created, but the observation form lacked a smart stat button to navigate directly to that CAPA record.
4. `hse.observation` did not inherit `mail.activity.mixin`, preventing managers from scheduling follow-up activities in chatter.

---

## Root Cause

1. **Manifest Demo Data Boundary:**
   Initial safety observations were declared exclusively inside `demo/demo_observations.xml` under the `'demo': [...]` section of `__manifest__.py`. In clean or pre-sales databases loaded with `--without-demo`, table `hse_observation` is completely empty.
2. **Default Filter Hiding Positive Reinforcement (Safe Acts):**
   The window action had `context="{'search_default_unsafe': 1}"`. Under BBS (Behavior-Based Safety) methodology (DuPont STOP / OSHA), recognizing safe acts is fundamental. Hiding safe acts by default contradicted the list view's color decoration (`decoration-success="obs_type == 'safe_act'"`).
3. **Missing Navigation and Location Fields:**
   `location` and `wbs_id` from `hse.project.mixin` were missing from the form and list views, and `button_box` lacked a stat button for `action_id`.

---

## Solution ✅

### 1. Model & Chatter Enhancements in `hse_observation.py`

Inherit `mail.activity.mixin` and add `action_view_action`:

```python
class HseObservation(models.Model):
    _name = 'hse.observation'
    _description = 'HSE Observation'
    _inherit = ['hse.project.mixin', 'mail.thread', 'mail.activity.mixin']

    def action_view_action(self) -> dict:
        """Smart button action to open the linked CAPA action."""
        self.ensure_one()
        if not self.action_id:
            return {}
        return {
            'type': 'ir.actions.act_window',
            'name': _('HSE Action (CAPA)'),
            'res_model': 'hse.action',
            'res_id': self.action_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
```

### 2. View Enhancements in `hse_observation_views.xml`

- **Smart Button:**
  ```xml
  <div class="oe_button_box" name="button_box">
      <button name="action_view_action" type="object" class="oe_stat_button" icon="fa-tasks" invisible="not action_id">
          <div class="o_stat_info">
              <span class="o_stat_text">CAPA Action</span>
          </div>
      </button>
  </div>
  ```
- **Location & WBS:** Add `location` and `wbs_id` in form Location group and `location` in tree view.
- **Search Filters:** Add dedicated filters for `Safe Acts`, `Unsafe Acts`, `Unsafe Conditions`, `Open`, `Action Raised`, `Closed`.
- **Default Context:** Set `context="{}"` in `action_hse_observation` so all BBS records are visible by default with their red and green badges.

### 3. Realistic BBS Seeding

Seed representative records across projects covering:
- `unsafe_act` with penalty & CAPA actions.
- `unsafe_condition` with CAPA actions.
- `safe_act` (positive safety behavior).

---

## ⚠️ Pitfalls

1. **Subcontractor Safety Score Couplings:** `subcontractor_evaluation_inherit.py` deducts 0.2 points per unsafe act/condition on `hse.observation`. Seeding must use valid subcontractor references.
2. **Polymorphic Reference in `hse.action`:** `source_ref` in `hse.action` is a `fields.Reference`. When linking an observation, format it as `'hse.observation,%s' % obs.id`.

---

## Verification

1. Open **Safety > Daily Operations > Observations (BBS)**: all records load immediately with red/green decorations.
2. Click an actioned observation: CAPA stat button appears in the button box and opens the related corrective action.
3. Test search filters: `Safe Acts`, `Unsafe Acts`, `Unsafe Conditions` filter accurately.
