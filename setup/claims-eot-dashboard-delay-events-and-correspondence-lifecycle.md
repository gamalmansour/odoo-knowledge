# Claims & EOT Dashboard, Delay Events, and Correspondence Lifecycle

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `claims`, `eot`, `delay-events`, `correspondence`, `dashboard`, `kanban`, `gtpl`, `fidic`, `time-bar`, `search-filters`

---

## Problem

When navigating to **Claims > Dashboard** (`action_claims_dashboard`), **Delay Events** (`action_claim_delay_event`), **Claims** (`action_claim_record`), or **Correspondence** (`action_claim_correspondence`):

1. **Empty Screens Across the Claims Module:**
   - In clean production environments or freshly restored client databases (`hadhoud_demo`), all four views opened with zero records.
   - Project directors and contract managers had no visibility into active contractual delay events, time-bar countdowns, or pending financial prolongation claims.
2. **Default Context Filter Traps:**
   - **Claims Action (`action_claim_record`):** Defaults to `{'search_default_filter_open': 1}`, which filters for `[('status', 'not in', ('determined', 'closed'))]`. If all claims in the system are settled or closed, the list view renders completely empty, confusing users into believing records were deleted.
   - **Delay Events Action (`action_claim_delay_event`):** Defaults to `{'search_default_filter_open': 1}`, which filters for `[('state', 'in', ('logged', 'under_review'))]`. When all delay events are linked to claims, their state transitions to `'claimed'`, causing the delay events list to appear completely blank!
3. **Missing Foreign Key Relational Visibility:**
   - The field `claim_id` on `claim.delay.event` was added via an extension model (`claim_delay_event_ext.py`).
   - However, the form, tree, and search views of `claim.delay.event` omitted `claim_id`, preventing engineers from seeing which claim a delay event belonged to, or filtering/grouping delay events by claim.

---

## Root Cause

1. **Demo Data ID Mismatch:** The default `demo_claims.xml` and `demo_delay_events.xml` hardcode foreign key references to demo project XML IDs (`construction_project.demo_project_1`), which do not exist in databases created without demo data or seeded with real-world enterprise projects.
2. **Restrictive Action Filter Logic:** Default search filters assumed a continuous influx of raw, unclaimed delay events and unadjudicated claims, hiding resolved or claimed records unless specifically accounted for during seeding and daily operations.
3. **Incomplete XML View Extension:** The extension model `ClaimDelayEventExt` declared `claim_id`, but corresponding view fields were not injected into the base views.

---

## Solution ✅

### 1. Expose `claim_id` in `claim_delay_event_views.xml`

Add `claim_id` to form, tree, and search views:

```xml
<!-- Form View: Under Linked Records -->
<group string="Linked Records">
    <field name="claim_id" readonly="1" invisible="not claim_id"/>
    <field name="change_request_id" readonly="state in ('claimed', 'closed')"/>
    <field name="rfi_id" invisible="not has_construction_dcc" readonly="state in ('claimed', 'closed')"/>
    <field name="ncr_id" invisible="not has_construction_qaqc" readonly="state in ('claimed', 'closed')"/>
</group>

<!-- Tree View: List column -->
<field name="claim_id" optional="show"/>

<!-- Search View: Search field & Group By filter -->
<field name="claim_id"/>
<filter string="Claim" name="group_by_claim" context="{'group_by':'claim_id'}"/>
```

### 2. Balanced Lifecycle Data Architecture

When seeding claims and delay events:
- Ensure delay events contain **both claimed events** (linked to `claim.record` in state `'claimed'`) AND **unclaimed events** (in `'logged'` and `'under_review'` states) so the default `filter_open` renders data immediately upon opening.
- Ensure claims span across the Kanban stages (`notice_served`, `under_assessment`, `determined`) so the Claims Dashboard Kanban displays distribution metrics.
- Populate full statutory time-bar metrics (`event_date`, `notice_date`, `notice_due_date`, `time_bar_status`) and prolongation costs (`staff_prolongation_cost`, `equipment_idling_cost`, `daily_site_overhead`).
- Log contractual correspondence (`claim.correspondence`) with both outgoing notices and incoming determination letters.

---

## ⚠️ Pitfalls

1. **State vs Status Field Naming:**
   - In `claim.record`, the workflow field is named `status` (selection: `draft`, `notice_served`, `particulars_submitted`, `under_assessment`, `determined`, `closed`), NOT `state`.
   - In `claim.delay.event`, the workflow field is named `state` (selection: `logged`, `under_review`, `claimed`, `closed`).
   - Using the wrong field name in search domains or write calls raises an `AttributeError`.
2. **Automatic State Transition on Claim Linking:**
   - In `claim.record.write()`, assigning `delay_event_ids` automatically executes `rec.delay_event_ids.write({'state': 'claimed'})`. Do not manually attempt to force delay events to stay `'logged'` while linked to a claim.
3. **Monetary Currencies in List Views:**
   - When displaying `<field name="claimed_amount" sum="Total"/>` in tree views, the `currency_id` field MUST be included in the view (`<field name="currency_id" column_invisible="1"/>`), otherwise Odoo renders monetary sums as dashes (`-`).

---

## Verification

```bash
# Verify Claims, Delay Events, and Correspondence records via Python CLI
python -c "
import odoo
from odoo import api, SUPERUSER_ID
odoo.tools.config.parse_config(['-c', '/Users/gamal/odoo/odoo18.0/odoo18_con.conf', '-d', 'hadhoud_demo'])
with odoo.registry('hadhoud_demo').cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    print('Claims:', env['claim.record'].search_count([]))
    print('Delay Events:', env['claim.delay.event'].search_count([]))
    print('Open Delay Events:', env['claim.delay.event'].search_count([('state', 'in', ('logged', 'under_review'))]))
    print('Correspondence:', env['claim.correspondence'].search_count([]))
"
```

## References

- Best Practices: `Best Practices/saudi-gtpl-claims-eot-and-time-bar-defense.md`
- ORM: `orm/construction-seeding-field-pitfalls-dcc-qc-claims.md`
- Module: `construction_claims_eot`
