# PO Entries Without `#:` Reference Lines Are Silently Dropped

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc |
| Odoo Versions | 16, 17, 18, 19 |
| Severity      | 🔴 Critical |
| Last Verified | 2026-07-15 |
| Author        | ENG/Gamal Mansour |

**Tags:** `translation`, `i18n`, `po`, `references`, `occurrences`, `PoFileReader`, `qweb`, `polib`

---

## Problem

You hand-add (or hand-edit) entries in a module's `i18n/<lang>.po` — the `msgid`
and `msgstr` look perfect, `msgfmt -c` passes with **no errors**, yet after
`-u module --i18n-overwrite` (or `odoo-bin i18n import`) those specific
translations **never appear** in the UI. Everything else in the file translates
fine — only your hand-added block is ignored.

Typical hand-added (broken) entry — note it has a `#.` module comment but **no
`#:` reference line**:

```po
#. module: sale_visit
msgid "Skip Visit"
msgstr "تخطّي الزيارة"
```

## Root Cause

This is **not** a syntax error (so `msgfmt -c` stays silent) and **not** the
export-wipe issue. Odoo's `PoFileReader.__iter__` (`odoo/tools/translate.py`)
only yields a translation row **while looping over `entry.occurrences`** — the
`#:` reference lines:

```python
for occurrence, line_number in entry.occurrences:
    match = re.match(r'(model|model_terms):...', occurrence)   # -> model term
    ...
    match = re.match(r'(code):([\w/.]+)', occurrence)          # -> code term
    ...
```

If an entry has **zero `#:` occurrences**, the loop body never runs, **nothing
is yielded, and the entry is dropped completely** — as code *and* as model term.
The `#. module:` comment alone is not enough. (The reader also tries to
`self.pofile.merge()` a sibling `i18n/<module>.pot`; if that `.pot` file is
absent, the missing references are never back-filled either.)

The `#:` prefix is also what classifies the entry:
- `#: model:ir.model.fields,field_description:<mod>.field_x__y` → field label
- `#: model:ir.model.fields,help:<mod>.field_x__y` → field help
- `#: model:ir.model,name:<mod>.model_x` → model `_description`
- `#: model:ir.actions.act_window,name:<mod>.action_x` / `...,help:...` → action name / no-content
- `#: model:ir.ui.menu,name:<mod>.menu_x` → menu label
- `#: model_terms:ir.ui.view,arch_db:<mod>.view_x` → QWeb / view arch term
- `#: code:addons/<mod>/models/x.py:0` → Python `_()` (line number may be `0`)

## Solution ✅

**Never hand-write references — let Odoo generate them.** Export a fresh POT
from a DB where the module loads cleanly, then merge with `polib` (keeps
existing `msgstr`, adds correct `occurrences`).

```bash
# 1) Export the authoritative POT (READ-ONLY on the DB). Must run against a DB
#    where the module + ALL its depends are installed, or the model/view terms
#    are missing from the POT (code terms still appear — they come from the .py).
.venv/bin/python odoo-bin i18n export -c odoo.conf -d <db> -o /tmp/mod.pot <module>

# 2) Sync references onto the .po with polib (see snippet below).

# 3) Validate, then import for the target language only (no full -u needed).
msgfmt -c -o /dev/null <module>/i18n/ar_001.po
.venv/bin/python odoo-bin i18n import -c odoo.conf -d <db> -l ar_001 -w <module>/i18n/ar_001.po
```

```python
import polib
pot = polib.pofile("/tmp/mod.pot")
po  = polib.pofile("<module>/i18n/ar_001.po")
pot_by = {e.msgid: e for e in pot}
for e in po:
    pe = pot_by.get(e.msgid)
    if pe:                                   # keep msgstr, refresh references
        e.occurrences = list(pe.occurrences)
        e.comment, e.flags = pe.comment, list(pe.flags)
po.save()
```

Verify success in the DB (Odoo 16+ stores model/field translations in `jsonb`):

```sql
-- was <EMPTY> before the fix, shows Arabic after
SELECT name, field_description->>'ar_001'
FROM ir_model_fields WHERE model='sale.visit.skip.reason';
```

## ⚠️ Pitfalls

- **QWeb button text includes the inline markup.** Odoo extracts the whole text
  node, so the real `msgid` is `'<i class="fa fa-ban me-2"/> Skip Visit'`, **not**
  `"Skip Visit"`. A hand-added bare `"Skip Visit"` never matches the view term
  even once you add a reference. Always copy the exact `msgid` from the POT.
- **`msgfmt -c` will NOT catch this** — the file is syntactically valid. Green
  `msgfmt` ≠ translations will load.
- **Standard fields on a NEW model** (`active`, `sequence`, `name`, `create_uid`…)
  add fresh `field_description` occurrences to common msgids (`Active`,
  `Sequence`, `Reason`…). Those existing `.po` entries need the new occurrence
  merged in, or the new model's labels stay English.
- **Export from the right DB.** If a dependency is uninstalled (e.g.
  `base_geolocalize`), the module is skipped during load and its model/view terms
  vanish from the POT — only the `.py` code strings survive.
- Don't `text.replace()` PO files — use `polib` (handles line-wrapping & escaping).

## Verification

```bash
# Every non-header entry must have at least one occurrence:
python -c "import polib;print([e.msgid for e in polib.pofile('m/i18n/ar_001.po') if e.msgid and not e.occurrences])"
# -> [] means all good
```

## References

- Core: `odoo/tools/translate.py` → `class PoFileReader.__iter__`
- Related file: `misc/po-file-syntax-fatal-errors.md` (green msgfmt but partial load)
- Related file: `misc/translation-wiped-out-by-export.md` (the export-wipe sibling issue)
