# A Public-Token REST API Must Grade and Score Server-Side — the Client Number Is Never a Fact

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `controllers`, `rest-api`, `auth`, `public`, `token`, `sudo`, `integrity`, `race-condition`, `unique-index`, `rate-limit`

---

## Problem

A single-file web/mobile client authenticates against Odoo with a **shared token
embedded in the client itself** (GitHub Pages, an APK, a QR-code link). The
controller trusts the body:

```python
match = request.env["game.match"].sudo().create({
    "student_id": student.id,
    "goals":  min(max(int(data.get("goals") or 0), 0), 10),
    "points": min(max(int(data.get("points") or 0), 0), 2000),   # <-- forged in one line
})
```

Anyone who opens the developer console posts `points: 2000` forever. The
clamps look like validation but only bound the forgery; they do not prevent it.
Every aggregate built on that column — leaderboards, reports, the numbers a
pilot is judged on — is now fiction, and there is no way to tell a real row
from a forged one after the fact.

Two more defects usually travel with it:

* **A search-then-insert "once per day" rule.** `search_count(...) == 0` then
  `create(counted=True)` — two taps a few milliseconds apart both read zero and
  both count.
* **Unbounded creation.** The token is public, so one script can create
  unlimited child records overnight.

## Root Cause

The token is a *routing* credential (which tenant/group is this?), not an
*authentication* credential (is this caller who they claim to be?). It ships
inside the client, so it is public by construction, and treating any value that
arrives alongside it as trustworthy is a category error. `sudo()` in the
controller then removes the last layer that would have said no.

## Solution ✅

**1. Send inputs, never outcomes.** The client posts *what the user did*; the
server decides what it is worth.

```python
# body: {"answers": [{"question_id": 12, "chosen": "b", "ms": 3400}, ...]}
# NOT:  {"goals": 5, "points": 750}
```

Grade against the server's own record, as a stored compute so history
self-corrects when the reference data is fixed:

```python
class GameAnswer(models.Model):
    is_correct = fields.Boolean(compute="_compute_grade", store=True)
    points = fields.Integer(compute="_compute_grade", store=True)

    @api.depends("chosen", "question_id.correct", "answer_ms",
                 "match_id.group_id.question_seconds")
    def _compute_grade(self):
        for answer in self:
            answer.is_correct = answer.chosen == answer.question_id.correct
            ...
```

The parent's totals then become computes over the children — include the
one2many itself in `@api.depends`, or an `unlink()` leaves them stale:

```python
@api.depends("answer_ids", "answer_ids.is_correct", "answer_ids.points")
def _compute_score(self):
    for match in self:
        match.goals = len(match.answer_ids.filtered("is_correct"))
        match.points = sum(match.answer_ids.mapped("points"))
```

**2. Let the database enforce once-per-period**, not a Python read.

```python
_one_counted_per_day = models.UniqueIndex(          # Odoo 19; _sql_constraints is ignored
    "(student_id, date) WHERE counted IS TRUE",
    "This student already has a counted entry on this date.",
)
```

and retry the loser inside a savepoint instead of 500-ing:

```python
try:
    with request.env.cr.savepoint():
        return Match.create(dict(values, counted=True))
except psycopg2.IntegrityError:
    return Match.create(dict(values, counted=False))
```

**3. Bound what a leaked token can create** — caps on the parent record
(`max_children`, `max_per_day`), returning `403`/`429` rather than growing the
table.

**4. Re-validate every id from the request with a `search`, never `browse`.**

```python
allowed = set(request.env["game.question"].sudo().search([
    ("id", "in", posted_ids), ("active", "=", True),
    ("reviewed", "=", True), ("grade", "=", group.grade),
]).ids)
```

`sudo().browse(user_supplied_id)` is the IDOR shape — see
`security/portal-controller-sudo-browse-bypasses-record-rules-idor.md`.

**5. Ship a kill switch and a configurable origin** so a leak is a parameter
change, not a deploy:

```python
request.env["ir.config_parameter"].sudo().get_param("myapp.api_enabled", "1")
request.env["ir.config_parameter"].sudo().get_param("myapp.cors_origin", "*")
```

## ⚠️ Pitfalls

- **Clamping is not validating.** `min(max(int(x), 0), 2000)` bounds a forged
  number; it does not make it true. If the value is derivable server-side,
  never accept it at all.
- **An offline client may legitimately need the answer key** to give instant
  feedback. Ship it, but keep scoring server-side: the exposure drops from
  "any score" to "a perfect score", which is the natural cap and shows up
  immediately in a per-question success-rate field.
- **Catching `IntegrityError` without a savepoint aborts the whole
  transaction** — every later statement fails with `InFailedSqlTransaction`.
- **Grading as a stored compute depending on the reference record** is a
  feature, not a risk: fixing a wrong answer key re-grades everything already
  submitted. Decide deliberately whether you want that or a frozen snapshot.
- `type="http"` + `request.make_json_response(data, headers=[...])` is the
  right shape for a REST endpoint; `type="json"` imposes the JSON-RPC envelope.
- Add `save_session=False` on public routes so every anonymous call does not
  write a session row.

## Verification

```python
def test_submit_grades_on_the_server_and_ignores_client_points(self):
    _r, body = self._post({
        "token": "...", "name": "Ahmed",
        "points": 999999, "goals": 99,                      # forged
        "answers": [{"question_id": self.q.id, "chosen": "b", "ms": 0}],
    })
    self.assertEqual(body["points"], 150)                   # server's own number
```

```sql
-- the once-per-day guard is real, not advisory
\d+ game_match      -- shows: "game_match_one_counted_per_day" UNIQUE, (student_id, date) WHERE counted
```

## References

- Built in `phoenix/phoenix_arena/odoo/phoenix_arena/controllers/main.py` (Phoenix Arena 19.0.1.0.0),
  replacing a controller that accepted `points` from the body.
- Related: `security/portal-controller-sudo-browse-bypasses-record-rules-idor.md`
- Related: `backend/scoped-device-tokens-for-mobile-api-native-bearer-needs-global-keys.md`
- Related: `orm/one2many-cache-order-is-insertion-not-order-in-creating-transaction.md`
- Related: `Best Practices/odoo-19-warnings.md` (`_sql_constraints` → `models.Constraint`)
