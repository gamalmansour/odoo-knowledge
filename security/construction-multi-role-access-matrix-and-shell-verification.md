# Multi-Role Access Matrix (RACM) Verification in Odoo Shell and False-Pass Superuser Trap

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-23                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `rbac`, `access-control`, `ir.model.access`, `check_access`, `shell`, `odoo18`, `separation-of-duties`

---

## Problem

When verifying Role-Based Access Control (RBAC) and Segregation of Duties (SoD) via `odoo-bin shell` or CLI verification scripts, running:
```python
contract.with_user(site_engineer).write({'notes': 'Test'})
```
may silently **succeed** without raising an `AccessError`, leading developers to believe that security ACLs are broken or that the user has unauthorized write privileges on sensitive contracts, even when `ir.model.access.csv` strictly forbids it (`perm_write=False`).

## Root Cause

1. In `odoo-bin shell`, the default environment `env` is bound to `SUPERUSER_ID` (uid 1) with `env.su == True`.
2. When calling `record.with_user(user)`, if the parent environment has `su=True`, the ORM can inherit superuser bypass behavior unless explicitly created via `env(user=user, su=False)`.
3. Furthermore, unlike web client RPC controllers (`/web/dataset/call_kw`) which automatically call `check_access_rights(operation)` and `check_access_rule(operation)` before executing model operations, direct Python ORM method calls inside shell scripts do not automatically trigger ACL checks unless `Model.check_access(mode)` is invoked.

## Solution ✅

When conducting automated or manual Role-Based Access Matrix verification across personas (e.g., Site Engineer, QC Inspector, HSE Officer, Finance Manager, Cost Controller):

1. **Use `check_access(mode)` for Declarative ACL Auditing:**
```python
from odoo.exceptions import AccessError

# Verify that Site Engineer is blocked from writing to Owner Contracts
try:
    env['contract.owner'].with_user(site_eng).check_access('write')
    raise AssertionError("Security Breach: Site Engineer has write access to Owner Contracts!")
except AccessError:
    # PASS: Correctly blocked by ir.model.access.csv
    pass
```

2. **Always Strip Superuser Mode (`su=False`) When Instantiating User Environments:**
```python
user_env = env(user=site_eng, su=False)
contract = user_env['contract.owner'].browse(contract_id)
# Verify with explicit access checking
contract.check_access('write')
```

3. **Multi-Role Matrix Construction Standards:**
- **Site Engineer:** Read-only on Owner Contracts (`R---`), full access on Daily Site Reports (`RCW-`), blocked on Bank Guarantees (`----`).
- **QC Inspector:** Full authority on Cube Crushing Tests & NCRs (`RCWD`), blocked on EOT Claims & Contracts (`----`).
- **HSE Officer:** Full authority on Permits to Work PTW (`RCWD`), blocked on CPM Schedules (`----`).
- **Finance Manager:** Full authority on Bank Guarantees & Cashflow (`RCW-`), blocked on technical Inspections (`----`).
- **Cost / Claims Controller:** Full authority on EOT Claims & Backcharges (`RCWD`), blocked on HSE Permits (`----`).

## ⚠️ Pitfalls

- **Do NOT rely on bare `model.with_user(u).write()` in test scripts:** Always check `check_access('write')` or call `check_access_rights()` to mimic the exact behavior of the web client.
- **Watch out for wildcard `base.group_user` in custom add-ons:** Granting `perm_write=1` to `base.group_user` in `ir.model.access.csv` leaks edit permissions to every internal employee regardless of their role.

## Verification

Run the test suite script from the shell:
```bash
python3 odoo-bin shell -c odoo18_dev.conf -d odoo18_construction --no-http << 'EOF'
import sys
sys.path.append('/path/to/project/scratch')
import test_role_access_matrix
test_role_access_matrix.run_role_matrix_tests(env)
EOF
```
Expected output:
```text
RBAC Suite Summary: 11/11 Tests Passed Successfully (100% Compliance).
```

## References

- Related: `security/sod-approval-checks.md`
- Related: `backend/env-su-guard-silently-passes-in-transactioncase.md`
