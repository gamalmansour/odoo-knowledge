# Event-triggered reminder activities: dedicated activity type + auto-feedback, never summary-matching

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All (verified 19)                          |
| Severity      | 🟢 Low                                     |
| Last Verified | 2026-08-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `mail.activity`, `activity_schedule`, `activity_feedback`, `stock.picking`, `sale`, `invoice`, `automation`

---

## Problem

Business asks: "when the delivery is done, remind the salesperson (and the
coordinator) to create the invoice" — invoice-on-delivered-quantities policy.
Naive implementations create TODO activities keyed by a summary string, which
breaks dedup across languages, piles up stale reminders forever, and rings for
orders with nothing to invoice.

## Solution ✅ (verified in `solargy_sale_invoice_activity` 19.0.1.0.0)

1. **Hook the event, not a cron**: override `stock.picking._action_done()`;
   after super, filter `state == 'done' and picking_type_code == 'outgoing'
   and sale_id` and call the order-side scheduler (`deliveries.sale_id...`
   works on the multi-recordset).
2. **Dedicated `mail.activity.type`** (data record, `res_model: sale.order`)
   instead of summary matching — language-proof identification for both dedup
   (`activity_ids.filtered(lambda a: a.activity_type_id == type)`) and
   closing.
3. **Gate on real need**: skip when `invoice_status != 'to invoice'`
   (prepaid/fully-invoiced orders never ring). Reading the field after super
   is fresh — the qty_delivered → invoice_status recompute chain resolves on
   read.
4. **Dedup per user**: schedule only for target users not already holding an
   open activity of that type (`activity_ids` on the mixin holds only open
   ones — done activities are unlinked).
5. **Auto-close on fulfilment**: override `sale.order._create_invoices()` →
   `self.activity_feedback([TYPE_XMLID], feedback=...)`. Works because
   `activity_schedule()` creates activities with `automated=True` and
   `activity_feedback` defaults to `only_automated=True`; it closes the
   activity for every assignee at once.
6. Filter assignees with `not user.share`.

## ⚠️ Pitfalls

- **Never dedup/close by summary text** — summaries are rendered in the
  creator's language; a fresh entry per language defeats dedup and feedback.
- Without the auto-close (5), reminder activities accumulate for months and
  users start ignoring ALL activities — the feature kills itself.
- `activity_feedback` with a type whose activities were created manually
  (`automated=False`) silently skips them — pass `only_automated=False` then.
- Partial deliveries re-trigger by design (deliver → invoice → deliver again
  → new reminder), because the gate + dedup make re-triggering safe.

## Verification

Fresh-DB install, 4/4 tests: activity for salesperson + coordinators on
delivery validation, no duplicates on re-trigger, activities close on
`_create_invoices`, no activity when `invoice_status = 'invoiced'`.

## Related

- `orm/state-gated-action-button-must-be-idempotent-for-rerun.md`
- `security/data-cleaning-app-admin-only-least-privilege-operator-group.md`
  (the Sales Coordinator group reused as assignee)
