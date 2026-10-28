# Module Docstring in `__manifest__.py` Causes `WARNING: invalid module names, ignored`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All (15, 16, 17, 18, 19)                   |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-28                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `manifest`, `ast.literal_eval`, `invalid module names`, `module discovery`, `setup`

---

## Problem

When installing a newly created Odoo add-on with `-i <module_name>`, Odoo ignores the module during `update_list` and logs:

```text
WARNING <db> odoo.modules.loading: invalid module names, ignored: <module_name>
```

Even though the module directory is present in `addons_path` and contains both `__init__.py` and `__manifest__.py`.

## Root Cause

Odoo parses `__manifest__.py` using `ast.literal_eval(f.read())` in `odoo.modules.module.load_information_from_description_file`.
Unlike regular Python files, `ast.literal_eval` expects a **single Python expression** (the manifest dictionary `{...}`). If a developer or linter adds a top-level module docstring (`"""..."""`) above the dictionary literal, `ast.parse(node, mode='eval')` raises a `SyntaxError`, causing Odoo to silently treat the directory as not being a valid Odoo module.

## Solution ✅

Never place a Python docstring (`"""..."""`) at the top of `__manifest__.py`. Use only `#` comments (such as `# -*- coding: utf-8 -*-`) before the `{` dictionary literal:

```python
# -*- coding: utf-8 -*-
{
    'name': 'My Module',
    'version': '18.0.1.0.0',
    'author': 'ENG/Gamal Mansour',
    'depends': ['base'],
    'data': [],
    'installable': True,
}
```

## ⚠️ Pitfalls

- Automated PEP8/docstring linters (such as `pydocstyle` or `ruff` with `D100`) may flag `__manifest__.py` for missing a public module docstring. Always exclude `__manifest__.py` from `D100` checks rather than adding a docstring.

## Verification

```bash
python3 odoo-bin -c odoo.conf -d <db_name> -i <module_name> --stop-after-init
```
Confirm `Loading module <module_name>` appears in the server log without `invalid module names, ignored`.
