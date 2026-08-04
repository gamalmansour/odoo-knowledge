# Calendar privacy: colleagues see "Busy" only — flip the default via param + migrate STAMPED preferences

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 19                                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-08-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `calendar`, `privacy`, `calendar.default_privacy`, `res.users.settings`, `post_init_hook`, `flush`, `busy`

---

## Problem

Client: "anyone can open the Calendar and read anyone else's meeting details;
we want attendees/organizer to see everything and everyone else to see only a
Busy block". Odoo HAS the whole mechanism (`privacy`/`effective_privacy` on
`calendar.event` + the `_fetch_query` masking that renders name as *Busy* and
blanks the other fields) — it is just defeated by the **public default**.

## Root Cause / three traps

1. Odoo 19 reads the default from the system parameter
   **`calendar.default_privacy`** (default `'public'`) — but only as a
   *fallback*. `res.users.create()` **stamps** the param value into each
   user's `res.users.settings.calendar_default_privacy` at creation time, so
   flipping the param later fixes NEW users only; existing users keep their
   stamped `public`.
2. `res.users.write` **raises AccessError when anyone — including the
   admin — changes `calendar_default_privacy` of another user** (deliberate
   privacy guard), so an ORM loop over users cannot migrate the stamp; go
   through `res.users.settings` (or SQL).
3. The param **already exists** in real DBs — creating it as an
   `ir.config_parameter` XML record crashes install with
   `ir_config_parameter_key_uniq`; use `set_param()` (upsert) in the hook.

## Solution ✅ (verified in `solargy_calendar_privacy` 19.0.1.0.0)

No model overrides at all — one post_init_hook:

```python
def post_init_hook(env):
    env['ir.config_parameter'].sudo().set_param('calendar.default_privacy', 'private')
    env.flush_all()   # pending ORM writes would otherwise overwrite the SQL below
    env.cr.execute("""UPDATE res_users_settings
                         SET calendar_default_privacy = 'private'
                       WHERE calendar_default_privacy IS DISTINCT FROM 'private'""")
    env.cr.execute("""UPDATE calendar_event SET privacy = NULL
                       WHERE privacy IN ('public', 'confidential')""")
    env.invalidate_all()
```

- Events reset to `NULL` follow their owner's (now private) preference via
  `effective_privacy`; a deliberately re-marked Public event still works.
- `'confidential'` is included in the reset: it shows details to ALL internal
  users, which is exactly the complaint.

## ⚠️ Pitfalls

- **`env.flush_all()` BEFORE the raw SQL** — a pending cached ORM write
  flushed later (e.g. by `invalidate_all(flush=True)`) silently overwrites
  the SQL update. This bit us in the test before the fix.
- Test the masking with a REAL other-user read
  (`event.invalidate_recordset()` then `event.with_user(outsider).read()`
  → name == 'Busy', location False, start still visible) — the mask lives in
  `_fetch_query`, and stale cache from the creating env returns real values.
- Don't force `privacy='private'` on every event write unless asked — losing
  the ability to publish a company-wide event is a regression.

## Verification

Fresh-DB install, 4/4 tests: new users default private, outsider reads
Busy-only while organizer/attendee read full details, hook migrates stamped
prefs + explicit public events, deliberate public event stays visible.

## Related

- `orm/stored-compute-incomplete-depends-silent-staleness.md` (cache/flush mechanics)
- `security/data-cleaning-app-admin-only-least-privilege-operator-group.md`
