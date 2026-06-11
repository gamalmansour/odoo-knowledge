# Conditional Validation in Inherited Models using @api.constrains

## Problem
When using `@api.constrains` to validate fields in an inherited base model (like `sale.order`), the constraint will trigger for **all** records of that model across the entire system. This can block normal operations (e.g. creating standard Sales Orders) if the validation logic is specific to your custom module (e.g. Tour Registration).

**Example Error:**
```python
@api.constrains('offer_ids')
def _check_offer_ids_limit(self):
    for rec in self:
        # ⚠️ This triggers on EVERY sale.order, even non-tour ones!
        if len(rec.offer_ids) < 1:
            raise ValidationError(_("You must select at least 1 Offer."))
```

## Solution
Always scope your constraint checks using a domain identifier or boolean flag (e.g., `is_registration`) that distinguishes your custom logic from standard Odoo behavior.

**Correct Implementation:**
```python
@api.constrains('offer_ids')
def _check_offer_ids_limit(self):
    for rec in self:
        # ✅ Only validate if it's a tour registration order
        if rec.is_registration:
            if len(rec.offer_ids) < 1:
                raise ValidationError(_("You must select at least 1 Offer."))
            if len(rec.offer_ids) > 3:
                raise ValidationError(_("You cannot enter more than 3 Offers."))
```

## Details
- **Versions:** All Odoo versions
- **Tags:** `orm`, `constrains`, `inheritance`, `validation`, `sale.order`
- **Severity:** 🔴 Critical (can break core functionality)

## Pre-mortem Analysis / Risks
If you forget to condition your constraints on inherited core models, a client trying to create a basic Invoice or Quotation 6 months later will encounter mysterious ValidationErrors related to fields they don't even see on their screen, completely halting their business operations. Always sandbox inherited model logic.
