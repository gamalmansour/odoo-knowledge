# Clean-DB Install Verification Catches What Static Review Misses (demo-as-data scatter, missing fields in ir.rule domains)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `install`, `verification`, `demo`, `data`, `ir.rule`, `record-rules`, `clean-db`, `ci`

---

## Problem

> A multi-module suite "looks fine" under static/code review and even compiles, but is **dead-on-arrival on a clean database**. The only reliable way to surface this class of bug is an actual clean-DB install:
>
> ```bash
> odoo-bin -c odoo.conf -d throwaway_db -i mod_a,mod_b,... --without-demo=all --stop-after-init --log-level=warn
> ```
>
> Two install-blocking patterns repeatedly slip past static review:

```
# 1) A demo record referenced by a file loaded as real DATA
ValueError: External ID not found in the system: my_module.acc_custody
while parsing other_module/data/demo_company_config.xml

# 2) A record rule whose domain traverses to a field that does not exist
odoo.tools.convert.ParseError: while parsing my_module/security/record_rules.xml
Invalid domain: Invalid field construction.project.user_id in leaf ('user_id', '=', 1)
```

## Root Cause

1. **demo-as-data scatter:** demo records are placed under the manifest `'data'` key (or named `data/demo_*.xml`) instead of the `'demo'` key. They then (a) install into PRODUCTION, and (b) are loaded even with `--without-demo`, so when another module's *real* data references them they resolve at first but break the moment the referenced records are correctly moved to `'demo'`. Cross-module demo references (`project` demo → `contract` demo accounts) make this fragile.
2. **Missing field referenced across many rules:** a field like `construction.project.user_id` is assumed by 12 `ir.rule` domains (HSE, DLP) and several controller searches, but was never actually added to the model (only `project_manager_id` exists). `ir.rule` domains are validated at **install/load** for some models, so this crashes the registry build — but only for the *first* module whose rule is validated, hiding the rest.

## Solution ✅

```bash
# A) Make a clean-DB install a CI gate. Run BOTH modes:
odoo-bin -c odoo.conf -d verify --without-demo=all -i <all-leaf-modules> --stop-after-init   # models + XML + rules
odoo-bin -c odoo.conf -d verify_demo                 -i <all-leaf-modules> --stop-after-init   # also exercises demo data
# grep the log for ERROR/CRITICAL and "demo data failed to install".

# B) Find demo records misplaced under the data key (basename starts with 'demo'):
python - <<'PY'
import ast, os, glob
for m in glob.glob('*/__manifest__.py'):
    d = ast.literal_eval(open(m).read())
    bad = [f for f in d.get('data', []) if os.path.basename(f).startswith('demo')]
    if bad: print(os.path.dirname(m), bad)
PY
# Move every hit from 'data' to the 'demo' key. Verify no NON-demo file refs those ids first.

# C) For an "Invalid field X" in a rule domain: either ADD the field to the model
#    (best when many rules/controllers assume it — one field fixes all references)…
user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)
#    …or correct every domain to a valid path (e.g. project_manager_id.user_id).
```

## ⚠️ Pitfalls

- A wrapper that ends in `echo`/`tee` makes the background job report **exit 0** even when Odoo exited **255**. End the script with `exit $RC` (capture `RC=$?` right after `odoo-bin`) so the real status propagates.
- Demo failures are **non-fatal**: Odoo logs `Module X demo data failed to install, installed without demo data` and continues with exit 0. Always grep for that string — a green exit code does NOT mean the demo loaded.
- `--without-demo=all` is the fast model+XML+rules check; it will NOT catch demo-record bugs (e.g. a `required` FK a demo row omits). Run the with-demo pass too if you sell POC demo data.
- A `required=True` Many2one on a shared **mixin** + demo rows that only set a sibling FK (e.g. `period_id` but not `project_id`) → NOT NULL violation. Backfill in the mixin's `create()`: if `'period_id' in self._fields and not vals.get('project_id')`, derive it.
- `db_filter` in the conf can hide a freshly created verification DB from the web UI — irrelevant for `-i --stop-after-init`, but name the DB to match the filter if you then want to open it.

## Verification

```bash
# Both must print ODOO_EXIT=0 with no ERROR/CRITICAL and no "demo data failed":
grep -E "ERROR|CRITICAL|demo data failed" install.log
psql -d verify_demo -tA -c "SELECT name,state FROM ir_module_module WHERE name LIKE 'your_prefix_%';"
```

## References

- Related file: `backend/testing-projects-contract-constraints.md`
- Related file: `backend/demo_data_generation_constraints.md`
- Related file: `views/xml-load-order-manifest.md`
- Found during the `test_cons` construction-suite stabilization (audit said 3 modules had demo-as-data; a clean-DB install proved it was 8, plus a missing `construction.project.user_id` breaking 12 record rules).
