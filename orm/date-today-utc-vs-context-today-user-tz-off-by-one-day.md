# `fields.Date.today()` (UTC) vs `context_today()` (User TZ) — a Silent Off-By-One-Day That Only Shows After Midnight

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-05                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `dates`, `timezone`, `context_today`, `Date.today`, `invoice_date`, `period-cutoff`, `flaky-tests`

---

## Problem

A suite of tests that passed all day suddenly fails at night:

```
AssertionError: datetime.date(2026, 8, 5) != datetime.date(2026, 8, 4) : Date propagated from the sheet
AssertionError: 46 != 45          # days overdue
AssertionError: 20.27 != 20.0     # late-payment compensation (days ÷ 365)
```

Six unrelated tests across four modules, all one day / one unit apart. Nothing in the code changed.

## Root Cause

Two different "today" exist in Odoo and they are **not** the same date for part of every day:

| Call | Returns | At 02:49 Cairo (UTC+3) on Aug 5 |
|---|---|---|
| `fields.Date.today()` | today in **UTC** | `2026-08-04` |
| `fields.Date.context_today(rec)` | today in the **user's timezone** | `2026-08-05` |

Between midnight local and midnight UTC (3 hours in Cairo, 10+ in Sydney) the two disagree. A model whose default is `context_today` compared against a test/other model using `Date.today()` is off by exactly one day — every night.

This is not only a test problem. In construction it decides **which month a cost or certificate falls in**:

- `invoice_date` stamped with `Date.today()` on a certificate a user issues at 1 a.m. on the 1st of the month lands in the **previous month** — wrong accounting period, wrong VAT return.
- Overdue-day counts, late-payment compensation (`days ÷ 365`), and hire-day billing all shift by a day.
- Period cut-offs (progress billing periods, DLP windows) can admit or reject a record wrongly.

Audit the split with:
```bash
grep -rn 'context_today'      --include='*.py' . | wc -l   # 116
grep -rn 'fields.Date.today()' --include='*.py' . | wc -l   # 125
```
A near 50/50 split across one suite means the two conventions are being mixed freely.

## Solution ✅

**Pick user-local time for anything a human perceives as "today"** — work dates, entry dates, invoice dates, issue dates:

```python
# Model defaults
entry_date   = fields.Date(default=fields.Date.context_today)
invoice_date = fields.Date(default=fields.Date.context_today)

# Inside methods — needs a record for the tz
'invoice_date': fields.Date.context_today(rec),
due = fields.Date.add(fields.Date.context_today(rec), days=rec.payment_days)
```

Keep `Date.today()` (UTC) only for **system-internal, non-user-facing** stamps where a global clock is intended (cron watermarks, technical audit timestamps).

**In tests**, compare like with like — assert against the same helper the model uses, or freeze the clock.

## ⚠️ Pitfalls

- `context_today` **requires a record** (`fields.Date.context_today(self)`) — it reads the tz from `self.env.user`. Calling `fields.Date.context_today()` bare raises.
- A user with **no timezone set** falls back to UTC, so the bug hides for them and appears only for colleagues who set one.
- The failure window is **only a few hours a day**, so CI that runs each morning is green and the nightly run is red — classic "flaky test" that is actually a real defect.
- Do NOT "fix" the tests by loosening the assertion to a 1-day tolerance; that hides a genuine period-cutoff bug.
- `fields.Datetime.now()` is always UTC and correct as a timestamp — the ambiguity is only when a *date* is derived from it.

## Verification

```bash
# Reproduce deterministically: put the user's tz far ahead and run near the boundary
psql -d <db> -c "update res_users set tz='Pacific/Kiritimati' where id=2;"
./odoo-bin -c conf -d <db> -u <module> --test-enable --stop-after-init
```
Any test comparing a `context_today` default with `Date.today()` fails immediately.

## References

- Surfaced during UAT of the construction suite at 02:49 Cairo time (UTC still on the previous day): six tests across `construction_labor`, `construction_store_issue`, `construction_equipment`, `construction_contract` failed by exactly one day.
- Related file: `orm/testing_compute_fields.md`
