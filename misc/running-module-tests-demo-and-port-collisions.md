# Running Module Tests — Demo-vs-setUp Collisions and Multi-Instance Port 404s

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `testing`, `httpcase`, `demo-data`, `sql_constraints`, `multi-instance`, `port`, `test-tags`

---

## Problem

Two unrelated failures show up when you run a module's tests with `--test-enable` on a machine that already runs another Odoo instance:

1. **Every `HttpCase` request returns 404** even though the route exists — the test opens `http://127.0.0.1:<port>` and hits a *different*, already-running Odoo server bound to that port.
2. **`--test-enable` fails only when demo data is loaded**, with SQL unique-constraint or `code`-collision errors, while `--without-demo=all` is clean:

```
ERROR ... duplicate key value violates unique constraint "..._code_uniq"
# a TransactionCase/HttpCase setUp() created a record with a fixed code/name
# that also exists in the module's own demo XML.
```

## Root Cause

1. `odoo17_dev.conf` (or any conf) pins `http_port`. `HttpCase.url_open` targets that port. A second Odoo dev server already listening there answers the request → 404 against the wrong registry.
2. When demo loads, the module's `demo/*.xml` records exist in the test DB. A `setUp()` that hard-codes a unique field (`code='sports'`, `code='football'`, a unique phone, etc.) collides with the demo record carrying the same value.

## Solution ✅

```bash
# 1) Override the HTTP + gevent ports so HttpCase talks to ITS OWN test server.
#    Also use a THROWAWAY db, never a real one.
.venv/bin/python odoo-bin -c odoo17_dev.conf -d p1_cftest --db-filter='^p1_cftest$' \
  --http-port=8911 --gevent-port=8912 \
  -i mymodule --test-enable --test-tags /mymodule \
  --without-demo=all --stop-after-init --log-level=test 2>&1 | tail -80
# Expect: "0 failed, 0 error(s) of N tests". Confirm the startup "database:" line
# shows your throwaway db (proof you didn't touch a real one).

# 2) Fix the demo/setUp collision properly: give test fixtures unique codes that
#    demo never uses (e.g. code='sports_test'), OR namespace them. Do NOT rely on
#    --without-demo=all forever — a demo+test-enable run must also be clean.
```

## ⚠️ Pitfalls

- `--without-demo=all` *hides* the collision; it doesn't fix it. Keep it for fast iteration, but make `-i mod --test-enable` (with demo) green before shipping.
- Fixing a demo/test-code collision is a **separate change** from any feature refactor in the same file — commit it on its own (fix-first-then-refactor).
- Constraint-check "dirty" tests legitimately emit `ERROR ... violates ... constraint` lines in the log (they `assertRaises`). Judge success by the final `0 failed, 0 error(s)` summary, not by grepping for `ERROR`.
- Never let a test run create/drop/install into a real database. Force `-d <throwaway>` + `--db-filter` and verify the startup `database:` line.

## Verification

```bash
# Clean summary line + correct db:
... odoo.tests.result: 0 failed, 0 error(s) of 163 tests when loading database 'p1_cftest'
```

## References

- Related file: `setup/csrf-session-conflict-multi-instance.md` (multi-instance session/CSRF variant)
- Related file: `setup/clean-db-install-verification-demo-as-data-and-missing-rule-fields.md` (demo-as-data install verification)
