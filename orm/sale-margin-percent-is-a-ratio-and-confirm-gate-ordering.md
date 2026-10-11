# `margin_percent` Is a Ratio, Not a Percentage — and Where a Confirmation Gate Must Sit

| Field         | Value                    |
|---------------|--------------------------|
| Category      | orm                      |
| Odoo Versions | 15, 16, 17, 18           |
| Severity      | 🔴 Critical              |
| Last Verified | 2026-08-12               |
| Author        | Gamal Mansour            |

**Tags:** `sale_margin`, `margin_percent`, `sale.order`, `action_confirm`, `gate`, `super`, `ratio`, `percentage`, `validation`

---

## Problem

Two independent traps hit the same feature — "block confirming a sales order
below a minimum profit margin".

**1. The field is a ratio.** `sale_margin` computes:

```python
# addons/sale_margin/models/sale_order.py
order.margin_percent = order.amount_untaxed and order.margin / order.amount_untaxed
```

A 20% margin is stored as **`0.2`**. The field is *labelled* `Margin (%)` and is
rendered through a percentage widget, so every screen, every export and every
conversation says "20". Compare a user-entered `20` against `margin_percent`
directly and **every order is blocked**; compare `0.2` against a field the user
filled with `20` and **nothing ever is**. Both failure modes look like the
feature "not working" rather than a units bug.

**2. Where the check runs decides whether it runs at all.** A system that has
lived a few years usually has several modules overriding
`sale.order.action_confirm`. If any of them returns a **wizard action** instead
of raising — a very common "warn then confirm anyway" pattern — then a gate
placed *after* `super()` never executes: the wizard short-circuits the call and
the order is later confirmed through the wizard's own path.

## Root Cause

`margin_percent` is a plain `Float`. The `%` lives in the label and the widget,
not in the value — the ORM stores exactly what the formula produced.

For the ordering: `action_confirm` is a chain, and each override decides whether
to call `super()`, when, and what to return. Nothing guarantees a gate written
today runs before a wizard written by another module three years ago.

## Solution ✅

**Normalise once, at the comparison, and say so.**

```python
actual = line.margin_percent * 100.0          # ratio -> human percentage
if float_compare(actual, floor, precision_digits=2) < 0:
    ...
```

Store the configured threshold the way a human types it (`12.5` means 12.5%) and
convert the Odoo field, never the other way round — users read and audit the
threshold, so it must look like what they said. Add a test that pins the units:

```python
def test_percent_is_read_as_a_percentage_not_a_ratio(self):
    self.Rule.create({'min_margin_percent': 20.0, ...})
    order = self._order(price=200.0)   # cost 100 -> exactly 50%
    order.action_confirm()             # must pass: 50 >= 20, not 0.5 >= 20
```

**Run the gate before `super()`:**

```python
def action_confirm(self):
    self._check_margin_floor()      # raises before anything happens
    return super().action_confirm()
```

Two reasons, both real:

- confirming first creates procurements and pickings that the raise then rolls
  back — wasted work, and noisy in the logs;
- it puts the check ahead of any sibling module whose override opens a wizard.

**Collect every violation, raise once.** A gate that raises on the first bad line
makes the user fix, retry, fix, retry. Build a list and put it all in one
`UserError`, naming each product and both numbers (actual and required).

## ⚠️ Pitfalls

- **Zero cost passes any floor, silently.** `purchase_price = 0` makes the margin
  100%. That is a missing-cost data problem, not a profitable sale, and it is the
  dangerous failure class because it looks like compliance. On the site above,
  307 order lines (0.6%) were in that state. Offer an explicit
  "block lines without a cost" switch — default it **off** so installing the
  module does not instantly block existing data.
- **Zero-priced lines break a per-line check.** Free-of-charge / bonus-goods
  deals put lines on the order at price 0; against a real cost that is −100%
  margin, so a per-line gate blocks every order carrying a giveaway. Skip them
  per line and let the whole-order check police the giveaway — that is the level
  where the economics actually live.
- **Check the historical distribution before agreeing a threshold.** On the site
  above, 2,853 confirmed orders sat at: 2.6% at a loss, 17% under 5%, 36% between
  5–10%. A "reasonable-sounding" 10% floor would have blocked **56% of everything
  they do**. That is a management decision, not a settings field — put the numbers
  in front of the sponsor before the module is switched on.
- **A per-category / per-customer-class rule matrix is worthless without the
  master data.** Confirm the classification exists *first*: on that site the
  customer-class table held **0 records** and 2,978 of 2,980 products sat in the
  root category, so every rule keyed on them would have resolved to the fallback
  forever. Always keep a global fallback so the control works on day one.
- **Ranking overlapping rules needs to be explicit and stored.** Use
  `parent_path.count('/')` as category depth so a leaf rule beats its parent's,
  and store the score so it can drive `_order` — otherwise `search(limit=1)`
  returns an arbitrary match and behaviour changes as rows are added.

## Verification

Odoo 18.0 Enterprise, against a 568 MB production copy, 16 tests passing —
covering the gate, the bypass group, the master switch, free lines in both
modes, missing cost, the full rule ladder (parent/child category, category vs
class, fallback), and a units test pinning percentage-vs-ratio.

Two environment notes found while testing there, both worth expecting elsewhere:

- `AccountTestInvoicingCommon` may fail to `setUpClass` on a heavily customised
  database (`ValueError: Expected singleton: product.template(...)`). A gate test
  needs no invoicing fixtures — plain `TransactionCase` runs everywhere.
- A salesperson confirming an order may lack `res.partner.credit_limit` read
  access, which another confirmation gate needs. Grant
  `account.group_account_invoice` to the test user, and note it in the README so
  the next person does not read it as a margin-related requirement.
