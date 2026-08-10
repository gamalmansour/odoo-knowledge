# Auditing an Inherited Odoo System — Get the Business Model and the Data Status First

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-10                                 |
| Author        | Gamal Mansour                              |

**Tags:** `implementation`, `audit`, `handover`, `takeover`, `brownfield`, `discovery`, `process`

---

## Problem

You are handed an existing Odoo system — built by developers who have left,
with no documentation, no version control, and no signed requirements — and asked
to understand it, audit it, or take it over.

The instinct is to start where the evidence is: read the modules, map the models,
run the flows, count the records. That produces a technically accurate report that
is **wrong in its conclusions**, and the errors are not obvious until someone who
knows the business reads it.

Two specific failures, both observed on a real 23-module brokerage project:

**1. Correct design filed as defects.** The commission engine deliberately excluded
one role from the manager cut cascade. Reported as a bug. It was correct — that
role is paid from a revenue-share split instead, which is invisible in the code
and only knowable from the business model. Several other findings had the same
shape: lead-withdrawal automation reported as "aggressive", a platform filter on
assignment quotas reported as "arbitrary". All three were core business logic.

**2. An entire analysis built on meaningless data.** The report's headline finding
was that the CRM held six months of steady usage while accounting had never been
touched — inferred from ~3,000 leads versus zero posted journal entries. A formal
open question was raised about the "contradiction". The client then said: all of
it is test data. Every volume-based conclusion, and the question itself, was void.

## Root Cause

An inherited system is not a greenfield project, and the standard implementation
phases assume one. Requirements normally flow from the business to the design; here
you are reading the design and trying to recover the business — backwards, and
lossy.

Code answers *what the system does*. It cannot answer *why*, *whether that is
correct*, or *whether anyone still wants it*. And record counts look like usage
evidence while being nothing of the sort until someone tells you whether the data
is real.

## Solution ✅

Run this order. Steps 1 and 2 are cheap, take one conversation, and change how
everything after them is read.

**1 — Get the business model, confirmed, in writing.**

State in three sentences how the client makes money: who pays whom, for what, in
which direction. If you cannot, you are not ready to audit.

The fastest route is to ask **"who do you work like?"** A comparable company name
transfers an entire operating model in one sentence. On the project above, "we work
like *[well-known proptech]*'s partner programme" instantly explained the franchise
companies, the dual invoicing, the lead-distribution machinery and the strict
company isolation — after three days of reverse-engineering had not.

**2 — Classify the data before inferring anything from it.**

Ask, and record: **real / test / imported / migrated**. Until answered, draw no
conclusion about usage, maturity, adoption or business damage from volumes.

Also open the records. Four contacts flagged as referral partners, named
`new lead` and a bare phone number, mean someone clicked a checkbox — not that a
referral channel exists.

**3 — Establish environment facts.**

Version, edition, localization, module inventory split into yours versus
third-party, and what is under version control.

**4 — Execute the core flow on a restored copy.**

Not from reading code. Restore, run it end to end, record what actually happened
including exact error text. Use `odoo shell` rather than the UI — more precise,
captures exceptions verbatim, and needs no password.

On the project above this found five blockers that static review had missed
entirely, including an automation rule that raised on every lead assignment
(blocking the system's primary process) and a commission tier table with an
uncovered range that silently paid zero.

**5 — Separate findings into three lists.**

| List | Meaning |
|---|---|
| **Broken** | Demonstrably wrong. Evidence attached. |
| **Unexplained** | You do not understand why it exists. **Not a defect yet.** |
| **Hygiene** | Not breaking today; raises the cost of every future change. |

Items leave *Unexplained* only when the business model confirms them wrong. Resolve
that list by asking, not assuming.

**6 — Report as a decision list, not a bug list.**

Each finding gets business impact and effort, so someone can decide what to fix
and what to accept. Group by consequence — money / operations / security /
compliance / hygiene — not by module.

## ⚠️ Pitfalls

- **Version control first.** If the addons directory is not in git, that is finding
  number one regardless of what else you found. Fix it before any other change —
  otherwise nothing is reversible or attributable.
- **Don't let inferred requirements become facts.** A feature in code proves
  somebody once asked for something; not that it was built right, matched the
  request, or is still wanted. Mark everything recovered from code as provisional.
- **Silent failures are the dangerous class.** Wrong configuration that produces
  zeroes and empty dashboards instead of errors will not be found in testing. Call
  these out explicitly and say how to detect them.
- **Don't audit the client's live or shared database.** Restore a copy. A full
  cycle creates records that cannot be undone.
- **Never ask for or enter credentials.** `odoo shell` connects directly and gives
  better diagnostics than the UI.
- **Say what you did not check.** An audit that does not state its own boundaries
  will be read as complete.

## Verification

You are ready to write findings when you can answer all of these:

```
1. How does the client make money, in three sentences?     → confirmed by client
2. Is the data real, test, imported, or migrated?          → confirmed by client
3. Did you run the core flow yourself, end to end?         → on a restored copy
4. Which findings are you unsure are defects at all?       → the Unexplained list
5. Is the addons directory in version control?             → yes, or it is finding #1
```

Any "no" means the report is premature.

## References

- Related file: `Best Practices/module-name-collision.md`
- Related file: `setup/neutralized-test-backup-in-production-reactivate-crons-from-source-defaults.md`
- Related file: `orm/undecorated-create-override-breaks-ui-creation-only.md`
