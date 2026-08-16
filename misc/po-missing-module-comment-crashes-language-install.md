# A .po file without `#. module:` crashes language install; without `#:` it translates nothing

| Field         | Value |
|---------------|-------|
| Category      | misc / translation |
| Odoo Versions | 16, 17, 18 |
| Severity      | 🔴 Critical |
| Last Verified | 2026-08-16 |
| Author        | Gamal Mansour |

**Tags:** `translation`, `i18n`, `po`, `language-install`, `hand-written-po`, `occurrences`

---

## Problem

Installing a language — any language — dies with a traceback that names no
file, no module and no line:

```
File "odoo/addons/base/wizard/base_language_install.py", line 40, in lang_install
File "odoo/addons/base/models/ir_module.py", line 977, in _load_module_terms
File "odoo/tools/translate.py", line 1511, in _load
File "odoo/tools/translate.py", line 818, in __iter__
    _, module = match.groups()
                ^^^^^^^^^^^^
AttributeError: 'NoneType' object has no attribute 'groups'
```

The wizard aborts, the language is left half-installed, and nothing tells you
which of your 90 modules is at fault.

A second, quieter version of the same bug: the install *succeeds*, and not one
string is translated even though the `.po` file is full of correct
translations.

## Root Cause

`PoFileReader.__iter__` in `odoo/tools/translate.py` makes two demands of every
entry, and hand-written `.po` files usually satisfy neither:

```python
match = re.match(r"(module[s]?): (\w+)", entry.comment)
_, module = match.groups()          # <-- no guard. None.groups() -> AttributeError
for occurrence, line_number in entry.occurrences:
    ...                             # <-- no occurrences? loop body never runs
```

1. **`#. module: <name>` is mandatory.** It is a *translator comment* (`#.`),
   not a reference. Missing it, `re.match` returns `None` and the whole
   language install crashes — including for modules that are perfectly fine,
   because one bad file kills the run.
2. **`#: <occurrence>` decides whether anything is imported.** With no
   occurrence lines the `for` loop has nothing to iterate, so the entry yields
   nothing and is dropped **silently**. The file parses, the install succeeds,
   and the translation never appears.

A file that looks like this — the shape you get by hand-writing translations —
is broken on both counts:

```po
msgid "Medical Sample"
msgstr "عينة طبية"
```

## Solution ✅

Never hand-write `.po` files. Export the template from Odoo, which emits both
required parts, then merge your existing translations in by `msgid`:

```python
# in odoo-bin shell
import base64, polib, os
from odoo.modules.module import get_module_path

mod = env['ir.module.module'].search([('name', '=', 'my_module')])
w = env['base.language.export'].create({
    'lang': '__new__', 'format': 'po', 'modules': [(6, 0, mod.ids)]})
w.act_getfile()
pot = polib.pofile(base64.b64decode(w.data).decode())

path = os.path.join(get_module_path('my_module'), 'i18n', 'ar.po')
old = {e.msgid: e.msgstr for e in polib.pofile(path) if e.msgstr}
for e in pot:
    if old.get(e.msgid):
        e.msgstr = old[e.msgid]
pot.metadata['Language'] = 'ar'
pot.save(path)
```

Then reload: `odoo-bin -d DB -u my_module --i18n-overwrite`.

Anything left in `old` but absent from the export is a string that no longer
exists in the code — print those rather than dropping them quietly; they are
often translations that belong to a *different* module.

To find the culprit before you fix anything:

```python
import re, polib, glob, os
from odoo.modules.module import get_module_path
for m in env['ir.module.module'].search([('state', '=', 'installed')]).mapped('name'):
    p = get_module_path(m, display_warning=False)
    for po in glob.glob(os.path.join(p or '', 'i18n', '*.po')):
        for e in polib.pofile(po):
            if not re.match(r"(module[s]?): (\w+)", e.comment or ''):
                print('CRASHES:', m, os.path.basename(po), repr(e.msgid[:40])); break
```

## ⚠️ Pitfalls

- **`msgfmt` will not catch this.** The file is valid gettext. It is Odoo's
  extra convention that is violated, so every standard PO tool reports the file
  as clean.
- **Adding `#. module:` alone only stops the crash.** Entries still need `#:`
  occurrences to import anything. Fixing the crash and declaring victory leaves
  you with a module that installs fine and translates nothing.
- **Nobody notices until a client installs a language.** English-only
  development never touches this code path. Test a language install as part of
  the release gate, not on demo day.
- **One bad file blocks every module.** The failure is global, so the cost of a
  single hand-written file is the entire localisation.
- `res.partner.name` and `city` are **not translatable fields** — PO rows
  targeting them are imported and then dropped. See
  `models/partner-name-is-not-translatable.md`.

## Verification

```python
# a string that was previously untouched should now come back translated
env['ir.model'].search([('model', '=', 'medical.content')], limit=1)\
    .with_context(lang='ar_001').name
# -> 'محتوى ترويجي معتمد'
```

And the install itself must complete:

```python
env['base.language.install'].create({'lang_ids': [(6, 0, lang.ids)]}).lang_install()
```

## References

- `odoo/tools/translate.py` — `PoFileReader.__iter__`
- Related: `misc/po-file-syntax-fatal-errors.md` (quotes, duplicate msgid)
- Related: `misc/translation-wiped-out-by-export.md`
