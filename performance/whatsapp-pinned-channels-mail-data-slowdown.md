# Custom WhatsApp Integrations Leave Thousands of `discuss.channel` Memberships Pinned, Causing 10,000+ SQL Queries on `POST /mail/data`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | performance                                |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-25                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `discuss.channel.member`, `whatsapp`, `mail/data`, `autovacuum`, `unpin_dt`, `performance`

---

## Problem

Every page load or browser refresh triggers `POST /mail/data` with **10,000–15,000 SQL queries** taking **4–14 seconds**, making the entire Odoo backend feel sluggish on Odoo.sh, external servers, and local machines alike:

```
INFO db werkzeug: "POST /mail/data HTTP/1.1" 200 - 14620 9.059 4.761
```

## Root Cause

Odoo Enterprise's official `whatsapp` module includes an `@api.autovacuum` hook (`discuss.channel.member._gc_unpin_whatsapp_channels`) that sets `unpin_dt` on inactive WhatsApp channels. Third-party or custom WhatsApp modules (such as `dev_whatsapp_integration`) create `discuss.channel` records with `channel_type = 'whatsapp'` and auto-add operators/admin as members **without** implementing an auto-unpin hook.

Over months, thousands of WhatsApp memberships accumulate with `unpin_dt IS NULL` (e.g., 2,773 channels / 5,546 pinned memberships, 2,406 on Admin alone). Because `discuss.channel.member.is_pinned` is True whenever `unpin_dt IS NULL`, `/mail/data` loads every single historical WhatsApp channel, its messages, and its partners on every page load.

## Solution ✅

1. Add an `@api.autovacuum` method on `discuss.channel.member` in the custom companion module to unpin inactive WhatsApp memberships (configurable via `ir.config_parameter`: default 1 day for read channels, 5 days for unread channels):

```python
@api.autovacuum
def _gc_unpin_whatsapp_channels(self) -> None:
    self._unpin_inactive_whatsapp_channels(limit=1000, notify_bus=True)
```

2. Ship an **idempotent one-shot `ir.actions.server`** (`<data noupdate="1">`) for production adoption after upgrade so existing backlogs are cleared immediately in bounded keyset-paginated batches (`id > min_id`, `order="id asc"`, `notify_bus=False`) without touching business data during module upgrade.

## ⚠️ Pitfalls

- **Do NOT rely solely on `channel_id.create_date`:** Odoo Enterprise's stock check (`channel_id.create_date <= five_days_ago`) can unpin an old channel where a customer just replied minutes ago. Always check `COALESCE(channel_id.last_interest_dt, channel_id.create_date)` and `member.last_interest_dt`.
- **Use keyset pagination (`id > min_id`) in batch loops:** Without it, a block of 1,000 recent-unread channels (between 1 and 5 days old) causes `search(limit=1000)` to return the same un-unpinned rows forever and terminate early before reaching older backlog rows.
- **Skip `_bus_send` in bulk one-shot cleanup:** Sending 5,000+ `discuss.channel/unpin` bus events in one click floods the WebSocket; reserve `_bus_send` for daily autovacuum.
- **Never delete channels or memberships:** Setting `unpin_dt = now` preserves all history and CRM links; any new inbound WhatsApp message updates `channel.last_interest_dt` and automatically re-pins the channel.

## Verification

```sql
SELECT count(*) FILTER (WHERE dcm.unpin_dt IS NULL) AS pinned_wa_memberships
FROM discuss_channel_member dcm
JOIN discuss_channel dc ON dc.id = dcm.channel_id
WHERE dc.channel_type = 'whatsapp';
```

After running the one-shot server action and refreshing the browser, verify `POST /mail/data` query count drops from 10,000+ to < 200 and response time drops below 0.5s.

## References

- Odoo 18 Enterprise reference: `enterprise/whatsapp/models/discuss_channel_member.py`
- Mail pinning logic: `addons/mail/models/discuss/discuss_channel_member.py`
