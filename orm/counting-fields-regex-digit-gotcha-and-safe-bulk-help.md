# Counting/auditing Odoo fields: `[a-zA-Z]*` regex silently misses Many2one — and how to safely bulk-add `help=`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-01                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `fields`, `regex`, `audit`, `help`, `documentation`, `many2one`, `tooling`, `coverage`

---

## Problem

When scripting/grepping to **count or audit field definitions** (e.g. "how many fields lack a `help=`?"), the intuitive regex silently **undercounts**:

```bash
# WRONG — misses every relational field
grep -c "fields\.[A-Z][a-zA-Z]*(" model.py
```

On a real 30-module suite this reported **1260** fields when the true count was **1896** — a **~33% undercount**. The danger: coverage math built on it looks "complete" (e.g. "100% of fields documented") while a third of the fields — the relational ones — were never even seen.

## Root Cause

`Many2one`, `One2many`, `Many2many` contain the **digit `2`**. The character class `[a-zA-Z]*` stops matching at `2`, so `fields.Many2one(` does **not** match `fields\.[A-Z][a-zA-Z]*\(`. Only digit-free type names (`Char`, `Boolean`, `Integer`, `Float`, `Selection`, `Date`, `Datetime`, `Text`, `Html`, `Monetary`, `Binary`, `Json`…) match. Relational fields — often the majority — are invisible to the count.

## Solution ✅

**1. Use a regex that allows digits after the first letter:**

```bash
# CORRECT — includes Many2one / One2many / Many2many
grep -cE "fields\.[A-Z][A-Za-z0-9]*\(" model.py
```

**2. For bulk-adding `help=` across many modules, drive it with a fan-out + verify pipeline and lean on deterministic checks — not on the agents' self-reports:**

- **One work unit per model file** (not per module): balances load and shrinks blast radius. Files are independent → parallel edits never conflict → no git worktrees needed.
- Each worker adds `help="..."` to every field. For **computed** fields it must open the `_compute_xxx` method and describe the *actual* formula (prefix `Computed:`), not guess. For **related** fields, mirror the source. **Never wrap `help=` in `_()`** (see `orm/avoid-translation-in-field-definitions.md`).
- **Per-file self-check inside each worker:** `python3 -m py_compile <file>` must exit 0 (a malformed edit is caught immediately), and the corrected-regex field count must be unchanged (you only ADD `help`, never remove/merge a field). Prefer targeted `Edit` calls; **never** rewrite the whole file with `Write` (silent truncation/data-loss risk).
- **Global deterministic verification (main loop, the source of truth):** after the run, re-`py_compile` everything, recount `fields` vs `help=` per file with the corrected regex, and flag any file where `help_count < field_count`. This — not the workflow's own report — decides what still needs work. It also self-heals against API-dropped workers.
- **Adversarial formula audit:** a second skeptical pass over the computed-heavy files re-reads each `_compute_` method and rewrites any `Computed:` help that is vague/wrong/backwards. In practice ~97% were already accurate; the ~3% fixed were missing a detail (a `*100`, a `max(x,0)` floor, an extra state like `invoiced`).

## ⚠️ Pitfalls

- **Duplicate `help=` is self-detecting:** two `help=` kwargs on one field is a Python `SyntaxError` (duplicate keyword arg) → `py_compile` fails. So "0 compile failures" also proves no field got a double `help`.
- **API-failed worker ≠ unedited file.** A worker can apply all its `Edit`s and then die on the *final* response ("Connection closed mid-response"). The file is done; only the report is lost. Trust the on-disk coverage scan, not the failure list.
- Don't compare "before vs after" field counts with the broken regex on one side and the corrected on the other — you'll invent phantom deltas. Pick one regex (the corrected one) for both.
- `help=` on fields is **not** wrapped in `_()`; Odoo extracts it for translation automatically. Writing English source is correct; Arabic goes in `i18n/ar.po` as a **separate** step (regenerate `.po` after adding the source terms).

## Verification

```bash
# 100% coverage: every field has a help=, nothing lost, nothing broken
python3 - <<'PY'
import re, glob
FIELD = re.compile(r'fields\.[A-Z][A-Za-z0-9]*\(')   # corrected
HELP  = re.compile(r'\bhelp\s*=')
tot=cov=bad=0
for f in glob.glob('**/models/*.py', recursive=True):
    if f.endswith('__init__.py'): continue
    s=open(f).read(); fc=len(FIELD.findall(s))
    if not fc: continue
    hc=len(HELP.findall(s)); tot+=fc; cov+=min(hc,fc)
    try: compile(s,f,'exec')
    except SyntaxError: bad+=1; print('COMPILE FAIL',f)
    if hc<fc: print(f'MISSING {fc-hc}: {f}')
print(f'coverage {cov}/{tot} = {100*cov//tot}%  compile_failures={bad}')
PY
```

## References

- Related file: `orm/avoid-translation-in-field-definitions.md` (why `help=` must not use `_()`)
- Related file: `orm/testing_compute_fields.md`
- Applied on the `test_cons` construction suite (30 modules, 144 model files, 1896 fields → 100% help coverage).
