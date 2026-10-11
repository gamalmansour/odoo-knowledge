# Selection-label Arabic translations need ir.model.fields.selection occurrence lines in the .po

**Category:** ORM / i18n
**Date:** 2026-07-26
**Project:** activity (Batch-3: event status labels "same for both languages")

## Symptom
API returns `status_label_ar == status_label_en` even though the serializer reads the selection label via `with_context(lang='ar_001')` and the module ships an `ar.po`. Client: "the value in API is same for both languages".

## Root cause
Selection labels don't translate through plain `msgid/msgstr` pairs alone. Odoo loads them through **`ir.model.fields.selection` reflection**, which requires the po entry to carry the matching occurrence comment line:
```
#. module: activity_media
#: model:ir.model.fields.selection,name:activity_media.selection__activity_event__status__upcoming
msgid "Upcoming"
msgstr "قادم"
```
Without the `#:` occurrence line the entry is dead weight — nothing links it to the selection value. Also: a missing `#. module:` comment line CRASHES Odoo's po reader (`AttributeError: 'NoneType' object has no attribute 'groups'`), silently killing the whole file's load in tests.

## Related trap (same batch)
`fields.Html(sanitize=True)` uses a **callable** `translate` — `update_field_translations` for it takes `{lang: {old_term: new_term}}` (per-term mapping), NOT a whole-string value like Char/Text.

## Rule of thumb
When "the Arabic label doesn't change": (1) check the po entry has the right `#:` occurrence line for the exact selection xmlid, (2) check every entry has its `#. module:` line, (3) write the test by actually loading the po (`_update_translations`) like Odoo core's `test_translate.py` — asserting the po file "contains the string" proves nothing.
