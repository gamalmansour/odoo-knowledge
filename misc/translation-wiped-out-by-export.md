# [Odoo i18n Export Wipes Out Existing Translations]

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc |
| Odoo Versions | All |
| Severity      | 🔴 Critical |
| Last Verified | 2026-06-08                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `translation`, `i18n`, `po`, `export`, `polib`

---

## Problem

> Describe the problem clearly. What happens? What error message do you see?

When you have an existing `ar.po` or `ar_001.po` file with manual translations and you run `odoo-bin i18n export` to update the file with newly added English strings, Odoo will export the *current state of the database*.
If any of your existing translations in the PO file were not successfully loaded into the database, or if there is a mismatch, the export command will **overwrite** the PO file and replace those translations with `msgstr ""`, effectively **wiping out** hundreds of existing Arabic translations.

```bash
# Running this command might wipe out your existing translations in the file!
odoo-bin i18n export -c odoo.conf -d my_db -l ar_001 --modules my_module /path/to/my_module/i18n/ar_001.po
```

## Root Cause

> Why does this happen? What is the underlying technical reason?

Odoo's i18n export doesn't merge new strings intelligently with the *file on disk*. It reads the source code for `msgid`s, then looks up the translation for the specified language (`ar_001`) inside the `ir.translation` table in the database. If it doesn't find it, it exports it as `msgstr ""`. Thus, any translation in the file that isn't fully synced to the DB gets destroyed.

## Solution ✅

> Step-by-step solution. Include exact commands and code.

Instead of trying to manually fix hundreds of wiped out strings or using regex/replace, use the Python `polib` library to intelligently inject translations into the exported PO file. `polib` handles multi-line string wrapping natively.

```python
# Step 1: Run the export command to get all strings (even if it wipes some out)
# Step 2: Use this script to restore translations securely using polib

import polib

file_path = "/path/to/my_module/i18n/ar_001.po"
po = polib.pofile(file_path)

translations = {
    "English String 1": "الترجمة العربية 1",
    "English String 2": "الترجمة العربية 2",
}

count = 0
for entry in po:
    if not entry.msgstr:  # Only update empty ones
        # Handle newlines if needed
        clean_msgid = entry.msgid.replace('\n', '\\n')
        if clean_msgid in translations:
            entry.msgstr = translations[clean_msgid]
            count += 1
        elif entry.msgid in translations:
            entry.msgstr = translations[entry.msgid]
            count += 1

po.save()
print(f"Successfully translated {count} new strings.")
```

## ⚠️ Pitfalls

- **Manual Text Replacement:** Do not use `text.replace()` or basic regex to update PO files! Odoo splits long strings into multiple lines at 80 characters. Standard string replace will fail to match these broken lines. Always use `polib`.
- **Language Code:** Make sure you name your file exactly matching the target language (e.g., `ar_001.po` for Egyptian Arabic). If you export using `-l ar_001` and the file is named `ar.po`, Odoo might get confused or ignore it on module upgrade.

## Verification

> How to confirm the fix actually worked?

```bash
# Verify the PO file syntax is correct after modification
msgfmt -c /path/to/my_module/i18n/ar_001.po
```

## References

- Related file: `misc/po-file-syntax-fatal-errors.md`
