# Route caller money/stock by the contact's company_id, not by country

**Category:** ORM / Multi-company / Money-routing
**Date:** 2026-07-22
**Project:** activity (client DB has 22+ companies, ALL in Saudi Arabia)

## Lesson
"One company per country" is a design assumption that real client DBs break freely — this one had 22+ same-country companies, so any `country → company` mapping degrades to "first company by sequence" (+ a warning) and silently routes carts/subscriptions/stock reads to the wrong company. The reliable key already exists in standard Odoo: **`res.partner.company_id`** — the contact's own company link, maintained by the client's own back-office anyway.

## Pattern
One resolver, partner-first with graceful fallbacks, accepting a priority chain:
```python
@api.model
def _company_for_partner(self, *partners):        # e.g. (child, guardian)
    partners = [p for p in partners if p]
    for p in partners:
        if p.company_id:
            return p.company_id                   # contact link wins
    for p in partners:
        if p.activity_country_id:
            return self._company_for_country(p.activity_country_id)  # fallback
    return self.env.company
```
Route EVERY caller-driven company decision through it (cart/checkout company, subscription company_id, coupon scoping, and `with_company()` stock-quantity reads — see [[stock-quantities-are-company-scoped-even-under-sudo]]).

## Rule of thumb
When a feature needs "which company does this customer belong to", check whether the client's data already answers it (partner.company_id) before inventing a mapping. Geographic mappings are defaults, not truths — always leave them as fallback, never the primary key.
