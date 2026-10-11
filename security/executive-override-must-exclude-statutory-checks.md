# An Executive Override Must Exclude Statutory Checks — and Must Log Every Bypass

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | All                                        |
| Severity      | 🟡 Important                               |
| Last Verified | 2026-08-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `approvals`, `workflow`, `override`, `audit-trail`, `compliance`

---

## Problem

> Sooner or later a client asks for it: *"the CEO presses Confirm and the system
> lets them through any warning we built."* Implemented literally, that request
> produces two silent defects:
>
> 1. **It opens gates that were never the company's to open.** Once `action_confirm`
>    carries a single `if is_ceo: skip everything`, it also skips the customer tax
>    ID, the mandatory fiscal field, the e-invoicing precondition. Those are not
>    approvals — no rank inside the company changes what the tax authority accepts —
>    and the order confirms into a document that gets rejected downstream, weeks
>    later, by someone with no interest in the org chart.
> 2. **The bypass leaves no trace.** The record shows a normal confirmation. Six
>    months on, nobody can tell a *decision was taken* from a *rule that quietly
>    did not apply*, and the approval history of every other order loses its
>    meaning too.

## Root Cause

> Guards accumulated in `action_confirm` across several modules look alike — they
> are all `raise UserError` — so they get treated as one category. They are two:
>
> | | Internal approval | Statutory / external validation |
> |---|---|---|
> | Who set the rule | the company | a tax authority, a bank, a regulator |
> | Who can waive it | somebody senior enough | **nobody in the company** |
> | Cost of skipping | a decision made faster | a document rejected downstream |
>
> An override is legitimate for the first kind and meaningless for the second.

## Solution ✅

> Put the predicate in the **lowest module of the dependency chain** — usually the
> one that defines the executive group — so every module above can call it without
> a new dependency, and classify each guard explicitly.

```python
# module A (low in the chain — it owns the group)
def _x_ceo_override(self) -> bool:
    """The top of every internal chain here. A gate that can still stop them
    is a gate they would open in two clicks anyway (approve, then confirm)."""
    return self.env.user.has_group(CEO_GROUP)

def _x_log_override(self, skipped: str) -> None:
    self.ensure_one()
    self.message_post(body=_(
        "Confirmed by %(user)s using the CEO override — %(skipped)s.",
        user=self.env.user.name, skipped=skipped))
```

```python
# module B (depends on A) — classify every guard
def action_confirm(self):
    for order in self:
        override = order._x_ceo_override()

        # INTERNAL — overridable
        if order.needs_flow:
            if not order.opportunity_id and not override:
                raise UserError(_("… must come from an opportunity."))
            if order.flow_state != 'approved':
                if override:
                    order.flow_state = 'approved'
                    order._x_log_override(order._x_override_summary())
                else:
                    order._x_request()
                    blocked |= order
                    continue

        # STATUTORY — NOT part of the override, deliberately after it
        order._check_customer_tax_id()
    ...
```

`_x_override_summary()` names each gate that was actually passed, so the chatter
message is specific (`"the approval chain, the CRM opportunity requirement"`)
rather than a generic "override used".

## ⚠️ Pitfalls

- **Grep every guard before writing the override.** They are spread across
  modules and easy to miss:
  `grep -n "raise UserError\|raise ValidationError" */models/<model>.py`.
  A guard you did not classify is a guard you classified by accident.
- **Do not widen the override to "senior management".** Giving it to the tier
  below the top empties the per-user limits of their meaning — that tier is
  exactly who the limits exist to bound. Write a test asserting the second-highest
  role is still stopped.
- **The override must set the approval state, not skip past it.** Leaving the
  order in `waiting` while confirming it produces a confirmed order that the
  approval list still shows as pending, and any later `write` re-triggers the flow.
- **Post to the chatter, not to the log file.** `_logger.info` is not an audit
  trail — nobody reads the server log when reviewing an order.
- **Ordering matters.** Put the statutory check after the override block and
  outside it, so no future edit to the override can accidentally enclose it.
- Related: [sod-approval-checks.md](sod-approval-checks.md) — the opposite
  direction, stopping a user approving their own record.

## Verification

```bash
./odoo-bin -c <conf> -d <db> -u <module> --test-enable \
    --test-tags /<module> --stop-after-init
```

Tests that must exist:
- the executive confirms above their own limit, and above every limit in the chain;
- the executive confirms an order refused earlier;
- **the executive is still stopped by the statutory check** (missing and malformed);
- the tier below the executive is NOT overridden;
- the chatter message names the person and each gate passed.

## Real Case

Solargy (Odoo 19.0): six guards across `solargy_sale_approval` and
`solargy_sale_b2b_flow`. Five were internal (discount ladder at three tiers, the
B2B/project chain, the CRM-opportunity requirement) and were opened. The sixth,
the 14-digit Egyptian national ID required by ETA on the invoice, was kept
enforced for everyone. 127 orders worth 43.9M EGP were waiting on approvals
nobody in the chain could grant.
