# A Guard With an `env.su` Bypass Silently Passes Every Test — `TransactionCase` Runs as the Superuser

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `testing`, `TransactionCase`, `with_user`, `superuser`, `env.su`, `sudo`, `false-positive`, `security`

---

## Problem

A `write()` / `unlink()` guard is written with the usual escape hatch so crons and module data are never blocked:

```python
def write(self, vals):
    if not (self.env.su or self.env.context.get('work_order_skip_lock')):
        ...
        raise UserError(...)
    return super().write(vals)
```

The tests that are supposed to prove the guard works fail with:

```
AssertionError: UserError not raised
```

The dangerous version of this is the opposite outcome: had the test been written as "the write succeeds", it would have gone **green** while the guard never ran even once. The whole test file would certify a feature that does nothing.

## Root Cause

`odoo.tests.common.TransactionCase` builds its environment as **`SUPERUSER_ID` (uid 1)**, not as the admin *user* and not as any normal user. So in every test `self.env.su` is `True`, and any guard that exempts the superuser is skipped before it can raise.

The same applies to anything else keyed on the superuser: `env.su`, `env.is_superuser()`, and `sudo()`-flavoured checks. It equally hides `ir.model.access` and `ir.rule` problems — the superuser bypasses those too.

## Solution ✅

Exercise the guard as a **real user**, which is the actual threat model — the guard exists to stop a person editing in the UI, not to stop a cron:

```python
def setUp(self):
    super().setUp()
    # TransactionCase's env runs as the SUPERUSER, which the lock deliberately
    # lets through (crons, module data). The lock protects real users, so the
    # edit attempts below are made as one.
    self.engineer = self.env['res.users'].with_context(no_reset_password=True).create({
        'name': 'Site Engineer', 'login': 'test_wo_lock_engineer',
        'groups_id': [(6, 0, [
            self.env.ref('base.group_user').id,                        # always include this
            self.env.ref('construction_project.group_project_manager').id,
        ])],
    })

def test_completed_work_order_refuses_content_edits(self):
    self.work_order.write({'state': 'completed'})                      # setup, as superuser: fine
    with self.assertRaises(UserError):
        self.work_order.with_user(self.engineer).write({'quantity_executed': 99.0})
```

Keep using the plain `self.env` for **fixture setup** (fast, no ACL noise) and `with_user()` only for the calls whose permission behaviour is under test. Then assert the bypass explicitly too, so both branches are covered:

```python
def test_bypasses(self):
    self.work_order.write({'state': 'completed'})
    self.work_order.with_user(self.engineer).with_context(
        work_order_skip_lock=True).write({'quantity_executed': 42.0})   # context key
    self.work_order.write({'quantity_executed': 43.0})                  # superuser (cron path)
```

## ⚠️ Pitfalls

- **A green suite is not evidence here.** Before trusting a permission/lock test, make it fail on purpose once — comment out the `raise` and confirm the test goes red. If it stays green, it was never running the guard.
- **`with_user()` on the record, not on `self.env`.** `record.with_user(u).write(...)` is what re-evaluates the guard for that write; changing the env afterwards does not retro-apply to an already-browsed recordset's write call.
- **Always add `base.group_user`** to a test user's `groups_id`. A `(6, 0, [...])` write replaces the whole set, and without the internal-user group the test dies on unrelated `AccessError`s instead of your guard. See `backend/testing-access-error-base-group-user.md`.
- **Same trap for `ir.rule` and ACL tests** — record rules never apply to the superuser, so a record-rule test written with plain `self.env` proves nothing.
- **Do not "fix" it by dropping the `env.su` bypass.** The bypass is what keeps crons, `ir.cron` running as `base.user_root`, and module data from crashing in production. Fix the test, not the guard.
- **Exempt-field lists need their own tests.** If the guard whitelists fields (`state`, the posted-move link, chatter fields), assert each one still writes as a real user — a typo in that set is invisible otherwise.

## Verification

```bash
./odoo-bin -c odoo17_dev.conf -d <db> -u construction_project --test-enable --stop-after-init
```

Confirmed on `project.work.order`'s completed-lock (Odoo 17): with plain `self.env` three tests reported `UserError not raised`; switching those writes to `with_user()` turned all 14 green with no change to the guard itself.

## References

- Implemented in `construction_project` v17.0.1.21.0 — `models/project_work_order.py`, `tests/test_work_order_requisition_and_lock.py`
- Related file: `backend/testing-access-error-base-group-user.md`
- Related file: `backend/assertraises-savepoint-rolls-back-pre-raise-writes.md`
