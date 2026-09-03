# XML Loader Destroys `%%` in View Archs — QWeb t-esc Literal Percent Crashes Portal Page (500)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `qweb`, `t-esc`, `portal`, `500`, `format-string`, `convert.py`, `percent`, `arch_db`, `report`, `str.format`

---

## Problem

A portal page (e.g. `/my/targets/<id>` target detail) returns **HTTP 500** for portal users:

```
ValueError: incomplete format
Template: sale_target.portal_target_detail
Element: <span ... t-esc="'%.1f%' % line.achievement_pct"/>
```

The maddening part: the XML file on disk contains the **correct** Python escape `t-esc="'%.1f%%' % line.achievement_pct"`, yet the DB `arch_db` shows a single `%` — and **re-running `-u` does NOT fix it**. The view's `write_date` updates on every upgrade, the file is correct, and the arch comes out broken every single time.

## Root Cause

Odoo's XML data loader mangles `%%` when loading any `<field type="xml">` / `<template>` arch. In `odoo/tools/convert.py` (`_tag_record`/template arch processing):

```python
def _process(s):
    # ... substitutes %(xml_id)d / %(xml_id)s references ...
    s = s.replace('%%', '%')  # "Quite weird but it's for (somewhat) backward compatibility sake"
    return s
```

Because the loader supports `%(module.xmlid)d` substitution inside archs, it also collapses **every** `%%` to `%` before storing the arch in `arch_db`. So a Python-correct format string `'%.1f%%'` in the source file is stored as the broken `'%.1f%'`, which raises `ValueError: incomplete format` the moment QWeb evaluates it.

Extra traps that made diagnosis harder:

- The crash is **data-dependent**: the element only renders when the surrounding `t-if`/`t-foreach` yields rows (here: a target WITH product carton lines), so installs/upgrades are green and empty records render fine.
- It's easy to misdiagnose as "stale arch_db vs fixed disk file" — the arch is NOT stale; it is faithfully re-mangled on every load.
- In Odoo 19 `arch_db` is JSONB per language; ALL language values get the mangled string.

## Solution ✅

Never rely on `%%` inside a view/template file. Move the literal percent OUT of the format string, as plain text next to the `t-esc`:

```xml
<!-- BROKEN after load: t-esc="'%.1f%%' % line.achievement_pct" on a self-closing span -->

<!-- CORRECT: -->
<span t-attf-class="badge rounded-pill #{...}">
    <t t-esc="'%.1f' % line.achievement_pct"/>%
</span>
```

**Cleaner still — use `str.format`, which has no escape for the loader to eat:**

```xml
<td><span t-esc="'{:.1f}%'.format(kpi.value)"/></td>
```

A single `%` passes through `_process()` untouched and `.format()` treats it as a plain
character, so the whole thing stays inside one expression instead of being split
between an expression and loose text. f-strings are not available in QWeb, so
`.format()` is the portable choice.

Alternative (ugly, not recommended): write `%%%%` in the file so the loader's collapse leaves `%%` in the DB.

Then upgrade the module and verify **in the DB**, per language:

```sql
SELECT key, lang.lang_key, (arch_db->>lang.lang_key ~ '%\.1f%''') AS has_broken_pct
FROM ir_ui_view, LATERAL jsonb_object_keys(arch_db) AS lang(lang_key)
WHERE key = 'module.template_name';
```

Finally, sweep the codebase for other landmines: `grep -rn "%%" custom/*/views/*.xml custom/*/data/*.xml custom/*/report/*.xml`.

## Also seen in: QWeb PDF reports (2026-09-03, Odoo 18)

Same root cause, different surface. Six report templates in one file; the three that
printed a percentage raised `ValueError: incomplete format` when rendered, the three
that did not were fine:

```
coverage             ValueError: incomplete format
frequency            OK
cycle_achievement    ValueError: incomplete format
coaching_trend       OK
territory_summary    ValueError: incomplete format
rep_performance      OK
```

The split along "does this report show a % sign" is the tell. It misdirects badly:
half the reports working makes it look like missing data for particular KPI types
rather than a template defect.

Here the failure only surfaces on **print** — the action returns an `ir.actions.report`
happily, the `ir.actions.report` record and the QWeb view both exist, and every
structural check passes. Render it to catch this:

```python
env['ir.actions.report']._render_qweb_html('module.report_x_document', [rec.id])
```

## ⚠️ Pitfalls

- **`-u` proves nothing here**: unlike most view bugs, re-upgrading rewrites the SAME broken arch. If the DB shows different content than the file after a fresh `-u`, suspect loader-side transformation (`%%` collapse, `%(xmlid)d` substitution), not staleness.
- **`dev=all` masks it**: with `dev=xml` views render straight from the (correct) file, so the developer sees a working page locally while every non-dev server 500s from the mangled DB arch.
- **`-u` on the wrong cluster**: machines with two PostgreSQL clusters (psql default 5432 vs conf 5433) — always check the startup log line `database: user@host:port` (see [odoo-silent-db-autocreate-masks-wrong-cluster](../setup/odoo-silent-db-autocreate-masks-wrong-cluster.md)).
- **Shell reproduction recipe (Odoo 19):** `MockRequest` moved to `odoo.addons.http_routing.tests.common`, and in `odoo shell` (no HTTP server) `HttpCase.http_port()` raises `AttributeError` — patch first: `HttpCase.http_port = classmethod(lambda cls: None)`, then `with MockRequest(env(user=rep.id)): env['ir.qweb']._render('module.template', values)` gives the real portal traceback without portal credentials.
- **The repair script is vulnerable to the same bug.** A Python one-liner written to
  fix this raises `ValueError: unsupported format character` on its own replacement
  text — `"'{:.1f}%'.format(%s)" % name` has a `%'` in it. Build the replacement by
  concatenation, not by `%`-formatting.
- **Preview EDITED templates before any `-u` (same recipe, one more line):** load the modified XML into the current transaction first — `from odoo.tools.convert import convert_file; convert_file(env, 'module', 'views/portal_templates.xml', None, mode='update', noupdate=False)` — then render via `MockRequest` and finish with `env.cr.rollback()`. Verifies new/changed QWeb end-to-end (including what the loader does to it, e.g. the `%%` collapse) without touching the DB.

## Verification

- Reproduced the exact `ValueError: incomplete format` by rendering the template as the real portal salesperson via `MockRequest` in `odoo shell`.
- Proved the loader mangling: file had `%%`, both `en_US` and `ar_001` arch values had `%`, and the view `write_date` confirmed a fresh `-u` had just rewritten it broken again.
- After moving the `%` outside the format string and re-upgrading, the DB regex check returns `f` and the page renders.

## References

- Core culprit: `odoo/tools/convert.py` → `_process()` → `s.replace('%%', '%')`
- Related file: [views/portal_templates.xml](file:///Users/gamal/odoo/odoo19.0/custom/sale_target/views/portal_templates.xml)
- Related KB: [xmlid-substitution-fails-in-python-field-domain](../orm/xmlid-substitution-fails-in-python-field-domain.md) (the flip side: where `%(xmlid)d` does NOT work), [odoo-silent-db-autocreate-masks-wrong-cluster](../setup/odoo-silent-db-autocreate-masks-wrong-cluster.md)
