# Browser tours: they skip silently, and an untested tour is decoration

| Field         | Value |
|---------------|-------|
| Category      | misc / testing |
| Odoo Versions | 17, 18 |
| Severity      | 🔴 Critical |
| Last Verified | 2026-08-16 |
| Author        | Gamal Mansour |

**Tags:** `testing`, `tours`, `HttpCase`, `websocket-client`, `mutation-testing`, `false-green`

---

## Problem

Six UI defects shipped past a 70/70 green Python suite — an action throwing
`Name 'ref' is not defined` on open, years rendered "2,023", percentages
rendered "2998%", hospital cards captioned with a doctor's sales tier. Every
one of them was invisible to `get_view`, which proves a view *compiles*, not
that a human can use it.

So we added HttpCase tours. First run:

```
skipped TestSaReferenceDataUi.test_institutions_screen : websocket-client module is not installed
0 failed, 0 error(s) of 16 tests
```

**Green. Having executed no browser code at all.** The exact failure mode the
tours were written to eliminate, now one layer up.

## Root Cause

Two independent traps:

1. **Odoo *skips* HttpCase tours when `websocket-client` is absent**, and a
   skipped test still counts toward "0 failed". Nothing in the summary line
   says the UI suite did not run. Chrome must also be installed.
2. **A tour that passes proves nothing about whether it would fail.** Selectors
   drift, a `run()` assertion reads the wrong property, a `:contains()` matches
   something it shouldn't — and the tour stays green forever.

## Solution ✅

**Fail loudly instead of skipping.** Add a plain `TransactionCase` alongside
the tours:

```python
@tagged('post_install', '-at_install')
class TestBrowserTestPrerequisites(TransactionCase):
    def test_websocket_client_is_installed(self):
        try:
            import websocket  # noqa: F401
        except ImportError:
            self.fail('websocket-client missing: every tour SKIPS and the '
                      'suite reports green while testing nothing. '
                      'pip install websocket-client')
```

**Mutation-test every tour.** Re-introduce each bug and confirm the tour goes
red at the right step:

```bash
cp -R $MODULE $BACKUP
# ... apply one defect ...
odoo-bin -d DB -u $MODULE --test-enable --test-tags "/$MODULE:TestUi.test_x" > mut.log
grep -q "0 failed, 0 error" mut.log && echo "NOT CAUGHT" || echo "caught"
rm -rf $MODULE && cp -R $BACKUP $MODULE
```

Assert the exact rendered string, so both directions of a bug fail. For a
percentage that must read `29.98%`, `:contains("29.98%")` rejects `2998%`
(widget double-count) *and* `30.00%` (`digits` rounding the stored value).

## ⚠️ Pitfalls

- **`start_tour(url_path, ...)` overrides the tour's own `url:`.** Pass the
  action path from Python, or the tour starts on `/odoo` and every trigger
  times out.
- **`admin` is not in your app's groups.** Tours hit AccessError on any
  group-gated model. Grant the group in `setUpClass` — it also documents which
  persona the screen is for.
- **Form many2one and char values live in an `<input>`**, so `innerText` is
  `""`. Reading only innerText reports every filled relation as empty:
  ```js
  const input = el.querySelector("input, textarea");
  return ((input ? input.value : el.innerText) || "").trim();
  ```
- **Negative assertions need `run()`**, not a trigger — throw with the
  offending text so a red run says what broke and how to fix it.
- Default step timeout is 10s; a slow first render can look like a real
  failure.

## Verification

```
tour succeeded
0 failed, 0 error(s) of 87 tests
```

plus a mutation run per defect showing `caught` for each.

## References

- `odoo/tests/common.py` — `HttpCase.start_tour`, `browser_js`
- Related: `misc/running-module-tests-demo-and-port-collisions.md`
