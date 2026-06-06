# PO File Syntax Fatal Errors Preventing Translation Loading

**Category:** Misc / Translation
**Tags:** `translation`, `i18n`, `po`, `syntax`, `msgfmt`, `quotes`
**Odoo Versions:** All Versions
**Severity:** 🔴 Critical
**Last Verified:** 2026-06-06

## 📝 Problem Statement

When manually translating or modifying `.po` files, developers often encounter a situation where translations simply **do not reflect** in the UI, even after correctly upgrading the module (`-u module_name`) or forcing a translation reload via the Odoo Developer Settings.

Often, only a few translations load (usually up to a certain point in the file), and the rest are completely ignored.

## ⚠️ Root Cause & Pitfalls

The root cause is almost always a **Syntax Error** or a **Fatal Error** in the `.po` file format. Odoo relies on strict PO parsing mechanisms (similar to GNU `gettext`). If the parser encounters a fatal error, it **aborts processing the rest of the file silently**.

The most common pitfalls that cause this crash are:

1. **Unescaped Quotes in Strings:**
   - **WRONG:** `msgstr "استخدم زر "حفظ" للمتابعة"`
   - **RIGHT:** `msgstr "استخدم زر \"حفظ\" للمتابعة"`
   - Putting raw `"` inside the string breaks the parser immediately.

2. **Duplicate Message Definitions (`msgid`):**
   - You cannot have the same `msgid` defined twice in the same `.po` file.
   - **WRONG:**
     ```po
     #: model_terms:ir.ui.view,arch_db:sale_visit.view_1
     msgid "Home"
     msgstr "الرئيسية"

     #: model_terms:ir.ui.view,arch_db:sale_visit.view_2
     msgid "Home"
     msgstr "الرئيسية"
     ```
   - **RIGHT:** (Combine the references)
     ```po
     #: model_terms:ir.ui.view,arch_db:sale_visit.view_1
     #: model_terms:ir.ui.view,arch_db:sale_visit.view_2
     msgid "Home"
     msgstr "الرئيسية"
     ```

## ✅ Solution & Best Practices

Before upgrading a module after heavy translation changes, **always validate the PO file**.

Run the following command in your terminal (requires `gettext` installed, standard on macOS/Linux):

```bash
msgfmt -c path/to/your/file.po
```

If the file has syntax errors or duplicate entries, `msgfmt` will output the exact line numbers causing the crash. Fix them until `msgfmt -c` returns no output (success).

Once fixed, run the module upgrade:
```bash
odoo-bin -c odoo.conf -u your_module_name
```
