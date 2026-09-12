# `safe_eval` in a Server Action Forbids Attribute Assignment (`STORE_ATTR`)

| Field         | Value                     |
|---------------|---------------------------|
| Category      | backend                   |
| Odoo Versions | All                       |
| Severity      | 🟡 Medium                 |
| Last Verified | 2026-09-12                |
| Author        | ENG/Gamal Mansour         |

**Tags:** `ir.actions.server`, `safe_eval`, `data-files`, `install-failure`

---

## Problem

A perfectly ordinary line inside an `ir.actions.server` `code` field aborts the whole
module install:

```python
old_rule.active = False
company.ksa_gosi_enabled = True
```

```
odoo.tools.convert.ParseError: while parsing .../data/server_actions.xml:8
forbidden opcode(s) in '...': STORE_ATTR
```

The failure happens at **parse time**, not when somebody runs the action, so the module
never finishes installing and the database is left mid-upgrade.

## Root Cause

Server-action code runs through `safe_eval`, which compiles the source and then rejects
any bytecode outside an allow-list. Assigning to an attribute compiles to `STORE_ATTR`,
which is not on it — the sandbox has no way to tell `record.active = False` from
`some_object.__class__ = X`, so it refuses the opcode wholesale.

Reading attributes (`LOAD_ATTR`) is fine, which is why the restriction surprises people:
`if old_rule.active:` passes and `old_rule.active = False` on the next line does not.

## Solution ✅

> Write through the ORM method instead of the attribute.

```python
old_rule.write({'active': False})
company.write({'ksa_gosi_enabled': True})
```

`write()` is a method call (`CALL`), not an attribute store, so the sandbox allows it. It
is also the better habit in a server action: one call per record set instead of one per
field, and it goes through the ORM's normal write path.

The same substitution applies to every place the pattern appears — `rec.state = 'done'`
becomes `rec.write({'state': 'done'})`.

## ⚠️ Pitfalls

- **Nothing warns you while writing the XML.** The file is well-formed, Python-valid, and
  passes a syntax check. Only Odoo's parser rejects it, and only on install/upgrade.
- Augmented assignment (`rec.counter += 1`) is the same opcode. Use
  `rec.write({'counter': rec.counter + 1})`.
- Subscript assignment on a local dict (`vals['x'] = 1`) is `STORE_SUBSCR` and **is**
  allowed — only attributes are blocked. So building a dict then calling `write()` works.
- The same sandbox governs `ir.cron` code, automated-action code and `amount_python_compute`
  on a salary rule. A rule that sets `payslip.some_field = x` fails identically.
- The error text dumps the entire code block into the log, which makes the real message
  (`STORE_ATTR`, at the very end) easy to miss. Search for `forbidden opcode` and read the
  last token.

## Verification

```bash
grep -nE "^\s*[a-z_]+\.[a-z_]+ *(\+|-)?= [^=]" <module>/data/*.xml   # inside <field name="code">
./odoo-bin -c <conf> -d <db> -i <module> --stop-after-init 2>&1 | grep -i "forbidden opcode"
```

## References

- Odoo source: `odoo/tools/safe_eval.py` (`_SAFE_OPCODES`, `test_expr`)
