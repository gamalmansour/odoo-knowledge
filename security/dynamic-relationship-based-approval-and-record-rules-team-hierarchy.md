# Decoupling Security and Approval Workflows from Static Job Roles via Dynamic Team Hierarchy (ReBAC)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `ir.rule`, `rebac`, `approvals`, `team-hierarchy`, `record-rules`, `crm.team`, `dynamic-authority`, `separation-of-duties`

---

## Problem

When business logic requires multi-tier organizational approvals (such as Deal/TCR approvals, commissions, purchase validations), developers often hardcode role groups (`res.groups`) or fixed M2o fields on the team (e.g. `sales_manager_id`, `sales_director_id`, `head_id`):

```python
# Hardcoded Anti-Pattern in Backend
def _check_tcr_approval_authority(self):
    allowed = (
        self.env.user.has_group('my_module.group_tcr_sales_manager')
        or self.env.user.has_group('my_module.group_tcr_sales_director')
    )
    if not allowed:
        raise UserError(_("Only a Sales Manager or Sales Director can approve!"))
```

```xml
<!-- Hardcoded Anti-Pattern in Record Rule -->
<record id="rule_tcr_manager" model="ir.rule">
    <field name="domain_force">['|', ('agent_id', '=', user.id), ('team_id.sales_manager_id', '=', user.id)]</field>
</record>
```

When the client expands or customizes their organization (e.g., adding intermediate roles such as `Team Leader`, `Senior Manager`, or custom franchise tiers), the entire security model breaks:
1. **Broken Visibility:** Intermediate supervisors cannot view their team members' records because `ir.rule` looks only at the agent or the static manager field.
2. **Hidden Buttons:** Approval buttons with static XML `groups="..."` remain invisible to custom supervisors.
3. **Execution Denial:** Even if the button is triggered via RPC, the hardcoded group check raises a blocking `UserError`.

## Root Cause

Role-Based Access Control (RBAC) based on static security groups cannot model dynamic, per-team organizational chains of command. When permissions depend on *who manages whom* within a specific team rather than a global blanket privilege, static groups fail.

## Solution ✅

Implement **Relationship-Based Access Control (ReBAC)** driven by a dynamic team hierarchy model (e.g. `crm.team.commission_hierarchy_ids`):

### 1. Dynamic Record Rules (XML)
Expand the record rule domain to dynamically inspect team hierarchy relationships:

```xml
<record id="rule_tcr_consultant" model="ir.rule">
    <field name="name">TCR: Consultant</field>
    <field name="model_id" ref="model_commission_tcr"/>
    <field name="groups" eval="[(4, ref('my_module.group_tcr_consultant'))]"/>
    <field name="domain_force">['|', ('agent_id', '=', user.id), ('team_id.commission_hierarchy_ids.user_id', '=', user.id)]</field>
</record>
```

### 2. Dynamic Hierarchy Authority Check & Self-Approval Prevention (Python)
In the business model, verify that the caller is strictly higher in the chain of command than the deal's owner (smaller sequence number):

```python
def _is_user_authorized_approver(self, user=None) -> bool:
    self.ensure_one()
    user = user or self.env.user

    # Superuser or Top-level Owner has universal authority
    if user._is_admin() or user.has_group('base.group_system') or user.has_group('my_module.group_franchise_owner'):
        return True

    # Segregation of Duties: agent cannot self-approve their own deal
    if user == self.agent_id:
        return False

    team = self.team_id
    if team and team.commission_hierarchy_ids:
        hierarchy_lines = team._commission_hierarchy()
        user_lines = hierarchy_lines.filtered(lambda l: l.user_id == user)
        if user_lines:
            agent_lines = hierarchy_lines.filtered(lambda l: l.user_id == self.agent_id)
            if agent_lines:
                # User must be strictly above the agent in the hierarchy
                return min(user_lines.mapped('sequence')) < min(agent_lines.mapped('sequence'))
            # Agent is not in hierarchy (standard salesperson), hierarchy supervisor is above them
            return True

    # Fallback to legacy fields/groups for backward compatibility
    if team and user in (team.sales_manager_id | team.sales_director_id | team.head_id):
        return True
    return False
```

### 3. Dynamic Button Visibility (View XML)
Add a non-stored computed field `can_approve_tcr = fields.Boolean(compute='_compute_can_approve_tcr')` and condition the UI button on it:

```xml
<field name="can_approve_tcr" invisible="1"/>
<button name="action_set_approved"
        type="object"
        string="Approve"
        class="btn-success"
        invisible="status not in ('waiting', 'operation_approve') or not can_approve_tcr"
        groups="my_module.group_tcr_consultant,my_module.group_tcr_sales_manager,..."/>
```

## ⚠️ Pitfalls

1. **Self-Approval Exploit (Segregation of Duties):** If you allow any member in `commission_hierarchy_ids` to approve without verifying `user != self.agent_id` and `user.sequence < agent.sequence`, a Team Leader who closes their own deal could approve their own commissions.
2. **Missing Group on Button XML:** If an approval button retains `groups="...manager,director"`, a Team Leader holding only the base Consultant group will have the button stripped from the DOM before Python evaluation. Always include the base group in `groups="..."` and gate visibility dynamically via `or not can_approve_tcr`.
3. **Empty Hierarchy Fallbacks:** During upgrades, existing teams will not have hierarchy records filled yet. Always maintain fallback logic to legacy role fields (`sales_manager_id`, etc.) so live operations never break.

## Verification

Run automated test verifying:
1. Leader with custom job title and only base consultant group can search and find subordinate deals via `ir.rule`.
2. `can_approve_tcr` computes `True` for the leader.
3. Subordinate agent cannot approve their own deal (`can_approve_tcr` is `False` and backend raises `UserError`).
