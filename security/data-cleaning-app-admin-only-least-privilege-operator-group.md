# Data Cleaning app is admin-only — grant an operator a least-privilege group (scoped by model)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 19 (Enterprise data_cleaning)              |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-08-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `data_cleaning`, `data_merge`, `deduplication`, `crm`, `acl`, `record-rule`, `least-privilege`, `groups`

---

## Problem

Client: a **Sales Coordinator** must merge duplicated leads through the Data
Cleaning app, "making sure that no higher authority is provided". But every
ACL of `data_cleaning`/`data_merge` models is **`base.group_system`** — out of
the box the only way to open the app is making the user a full Administrator.

## Solution ✅ (verified in `solargy_crm_dedup` 19.0.1.0.0)

Operator group + additive ACLs + model-scoped record rules:

1. **Group** `Sales Coordinator` (own `res.groups.privilege` section), implying
   `sales_team.group_sale_salesman_all_leads` — approving/merging is useless
   if record rules hide the underlying leads.
2. **ACLs — operator, not configurator:**
   - `data_merge.model`, `data_merge.rule`: **read only** (configuration
     stays admin).
   - `data_merge.group`, `data_merge.record`: read/write/**unlink**, no create
     (merge dissolves groups; discard writes records).
   - `crm.lead`: add an **unlink** row for the group — `data_merge_crm`
     implements `_merge_method` via the native CRM merge, which deletes the
     losing leads AS THE USER (salesman ACL has unlink=0, so without this row
     the merge raises AccessError).
3. **Record rules scoped by model** so "data cleaning access" ≠ "all models'
   data": `data_merge.model/group/record` all carry a **stored**
   `res_model_name` related — domain `[('res_model_name', '=', 'crm.lead')]`
   on the three rules, no dotted traversal (avoids the install-breaking
   ir.rule-invalid-path trap). Contacts/other dedup stays invisible.
4. Menus need nothing: Data Cleaning menus are ungated; `_visible_menu_ids`
   shows a menu when the user can read the action's model, so the app appears
   for the group automatically.

Adjacent client ask — "filter options for duplicated leads": core
`duplicate_lead_count` is a non-stored, non-searchable compute. Back the
filters with searchable Boolean computes whose `search=` resolves via
`_read_group([(fname, '!=', False)], [fname], ['__count'], having=[('__count', '>', 1)])`
on `email_normalized` / `phone_sanitized` (both indexed by core) and returns
`[(fname, 'in', duplicated_values)]`.

## ⚠️ Pitfalls

- Don't grant `data_merge.model/rule` write "to be safe" — that IS the higher
  authority the client excluded (an operator could point dedup at any model).
- The `crm.lead` unlink ACL is the non-obvious required piece; test the merge
  end-to-end with the operator user, not admin.
- Test the negative too: operator writing `data_merge.model` must raise
  `AccessError`, and a foreign-model dedup group must be invisible.
- `having=` in `_read_group` needs the aggregate in `aggregates` —
  `['__count']`.

## Verification

Fresh-DB install, 7/7 tests: duplicate email/phone filters (positive +
negative search), coordinator sees CRM dedup only, performs a real
`merge_records()` leaving one lead, and gets `AccessError` on any
configuration write; `has_group(base.group_system)` asserted False.

## Related

- `orm/odoo-19-res-groups-category-id-deprecation.md` (privilege/section recipe)
- `views/per-user-menu-hiding-leaks-through-group-keyed-visible-menu-cache.md`
  (menu visibility mechanics)
