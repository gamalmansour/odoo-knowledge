# A Cross-Module Flow Needs sudo at EVERY Actor Boundary — Found One at a Time Is Found Too Late

| Field         | Value        |
|---------------|--------------|
| Category      | security     |
| Odoo Versions | All          |
| Severity      | 🔴 Critical  |
| Last Verified | 2026-08-05   |
| Author        | ENG/Gamal Mansour |

**Tags:** `sudo`, `access-rights`, `cross-module`, `uat`, `account.move`, `actor-boundary`

---

## Problem

The equipment-hire billing flow crossed three modules and broke at **three different
places for three different users**, one after another:

1. The **fleet manager** pressed *Create Vendor Bill*:
   `AccessError: not allowed to create 'Journal Entry' (account.move)`
2. After fixing that, the same click died reading configuration:
   the profile lookup (`self.project_id.profile_id`) needs contract-module rights the
   fleet group does not have.
3. After fixing that, the **accountant** pressed *Post* on the bill:
   `AccessError: not allowed to access 'Equipment Record'` — posting mirrors the cost
   into `project.equipment.record`, a construction model the accountant rightly has no
   rights on.

Every fix revealed the next failure, because each was patched at the line that crashed
instead of at the boundary that owns it. All three had been invisible to a 77-test suite:
`TransactionCase` runs as SUPERUSER and never exercises ACLs.

## Root Cause

A business flow that crosses modules has **actor boundaries**: points where the acting
user changes (fleet → accounting) or where the data ownership changes (fleet → contracts
configuration → construction cost lines). Odoo executes everything as the clicking user,
so every read or write beyond that user's module fails — even when the operation is, from
the business's perspective, a system side effect or a configuration lookup.

The three failures are the three distinct boundary kinds:

| Boundary | Example here | Correct treatment |
|---|---|---|
| **Action that creates a document owned by another department** | fleet raises a vendor bill | `sudo()` the create; the business gate is the caller's own workflow (a confirmed contract), and the document lands in draft for the owning department |
| **Configuration read from another module** | which expense account the profile says to use | `sudo()` the read; configuration is aggregate metadata, not user data |
| **System side effect of another department's action** | posting the bill mirrors cost lines into the project | `sudo()` the side effect; the poster's job is posting, the mirror is the system's |

## Solution ✅

Fix the flow **as a whole**, walking it once per actor with that actor's real groups —
not one AccessError at a time:

```python
# 1) the document create — gate is action_confirm, bill lands in draft
move = self.env['account.move'].sudo().create({...})

# 2) the configuration read
profile = self.project_id.sudo().profile_id

# 3) the system side effect (called from account.move.action_post)
Rec = self.env['project.equipment.record'].sudo()
```

Plus read-only ACL so the raising user can open the document they created:

```csv
access_account_move_equipment_user_read,...,account.model_account_move,group_equipment_user,1,0,0,0
access_account_move_line_equipment_user_read,...,account.model_account_move_line,group_equipment_user,1,0,0,0
```

And pin each boundary with a test that uses the REAL minimal group, nothing more:

```python
def test_02_accountant_posts_without_construction_rights(self):
    acct = self._user('cycle_acct', ['base.group_user', 'account.group_account_invoice'])
    bill.with_user(acct).action_post()          # died before the fix
    self.assertEqual(bill.state, 'posted')
```

## ⚠️ Pitfalls

- **The UAT user's extra groups can mask boundary 2.** The manual UAT ran the fleet user
  with `group_site_engineer` as well, which implied contract read — the profile-read
  failure only surfaced in the regression test whose user had the equipment group alone.
  Test users must carry the *minimal* real-world group set.
- Do not fix boundary 1 by granting the fleet group create rights on `account.move` —
  that lets fleet users forge arbitrary journal entries. `sudo()` scoped to the one
  workflow action keeps the privilege exactly as wide as the button.
- Boundary 3 runs inside `action_post` of `account.move` — an override in *your* module
  executing for *their* user. Any model your override touches is your responsibility to
  sudo.
- Sweep the suite for siblings once one is found; this same trio was fixed earlier for
  subcontractor advance/progress bills, tender award, and work-order completion. Grep:
  `grep -rn "env\['account.move'\]\.create\|env\['account.move'\]\.sudo" --include='*.py'`

## Verification

Walk the cycle end-to-end **once per actor** with their minimal groups (shell script or
tests), not as admin:

```
clerk logs usage → fleet confirms hire + raises bill → accountant posts →
cost lines appear on the project — 27 checks, 0 failures
```

## References

- Related file: `backend/env-su-guard-silently-passes-in-transactioncase.md`
- Related file: `security/smart-button-counter-blocks-opening-the-form.md`
- Related file: `backend/assertraises-savepoint-rolls-back-pre-raise-writes.md`
