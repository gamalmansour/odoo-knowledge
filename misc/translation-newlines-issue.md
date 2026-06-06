# Translation Fails When Python String Contains Newlines

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-06-06                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `translation`, `i18n`, `po`, `newlines`, `UserError`

---

## Problem

> Even after successfully updating `.po` translation files and upgrading the module, certain translated strings still appear in English in the UI. This is particularly common in long validation messages or `UserError` exceptions where the string is split across multiple lines in Python.

```python
# Problematic code example
raise UserError(_(
    "Cannot close the visit: %(zero)d warehouse product(s) still have a "
    "quantity of zero. The maximum number of allowed zero-quantity "
    "warehouse products is %(max)d.\n\n"
    "Please fill in the missing warehouse quantities before closing."
) % {'zero': zero_count_wh, 'max': max_zeros_wh})
```

## Root Cause

> Odoo's translation matching is extremely strict. When Python evaluates implicitly concatenated strings that contain explicit newline characters (e.g., `\n\n`), the resulting compiled `msgid` often mismatches how `gettext` tools extract and format the `.po` file entries. If the exact literal string with all newlines and spaces does not perfectly match the `msgid` in the `.po` file (or if Odoo fails to parse the newlines cleanly from the `.po` syntax), the translation silently fails and falls back to the original English string.

## Solution ✅

> Simplify the text by removing `\n\n` entirely, making the error message a single continuous sentence. Use straightforward, single-line strings for `_()` translation markers.

```python
# Step 1: Simplify the Python string
raise UserError(_(
    "Cannot close the visit: %(zero)d warehouse product(s) still have a quantity of zero. The maximum allowed is %(max)d. Please fill missing quantities."
) % {'zero': zero_count_wh, 'max': max_zeros_wh})
```

```po
# Step 2: Ensure the .po file matches EXACTLY
msgid "Cannot close the visit: %(zero)d warehouse product(s) still have a quantity of zero. The maximum allowed is %(max)d. Please fill missing quantities."
msgstr "لا يمكن إغلاق الزيارة: يوجد %(zero)d منتج في المستودع لا يزال بكمية صفر. الحد الأقصى المسموح به هو %(max)d. يرجى استكمال الكميات الناقصة."
```

```bash
# Step 3: Upgrade module to sync translations
# From Odoo UI: Apps -> Update Apps List -> Upgrade module
```

## ⚠️ Pitfalls

- Using line breaks (`\n`) for visual formatting inside translated python exceptions is a common trap. It breaks Odoo's internal string matching for translations.
- Relying on automated `.po` generation without manually checking if the `msgid` actually perfectly matches the Python string runtime value.
- Forgetting to upgrade the module after fixing the `.po` file.

## Verification

> To confirm the fix worked: Trigger the validation error again. It should now appear in the correct target language (e.g., Arabic).
