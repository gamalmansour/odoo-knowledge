# `read_group` record count lives under `<groupby>_count`, not `__count`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18                                 |
| Severity      | 🟢 Low                                     |
| Last Verified | 2026-07-15                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `read_group`, `aggregation`, `count`, `KeyError`, `reporting`

---

## Problem

Building a KPI/aggregation with `read_group` and reading the per-group record
count as `__count` raises at request time:

```python
by_state = {g['state']: g['__count']                       # KeyError: '__count'
            for g in env['activity.subscription'].read_group([], [], ['state'])}
```

Passing `'__count'` in the `fields` list (`read_group([], ['__count'], ['state'])`)
does **not** create the key either.

## Root Cause

The classic `models.read_group()` returns, for each group dict, the record count
under **`'<first_groupby_field>_count'`** — e.g. grouping by `state` gives
`'state_count'`. `'__count'` is a key of the *newer* `_read_group` / web
`web_read_group` layer, not of `read_group`. Mixing the two conventions is the bug.

## Solution ✅

Read the `<groupby>_count` key (with a defensive fallback so the same helper works
if you later switch to `_read_group`):

```python
def _group_count(group, field):
    return group.get('__count') or group.get('%s_count' % field) or 0

by_state = {g['state']: _group_count(g, 'state')
            for g in Sub.read_group([], [], ['state'])}
```

For a plain aggregate (no groupby) use a measure and read it back:

```python
res = Sub.read_group([('state', 'in', ('confirmed', 'active'))], ['amount_total:sum'], [])
total = (res[0].get('amount_total') or 0.0) if res else 0.0
```

## ⚠️ Pitfalls

- Odoo 17 also ships the newer `_read_group(domain, groupby, aggregates)` which
  returns **tuples**, not dicts — different API again. Pick one and read its shape.
- The count key follows the **first** groupby only. With multiple groupby fields,
  the count is still `'<first>_count'`.
- `search_count` per bucket is a correct but chattier alternative when you only
  need a couple of counts.

## Verification

An HTTP/unit test that actually calls the endpoint surfaces this — a bare install
does not (the code path only runs when the aggregate is requested).

## References

- Code: `activity/activity_admin_api/controllers/admin_controller.py` (`_group_count`)
