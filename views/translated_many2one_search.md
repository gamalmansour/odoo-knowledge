# Translated Many2one Field Search in Odoo

## Problem
When a user sets their language to Arabic and searches for a customer by Arabic name in a standard `Many2one` field, the search may fail to find the customer if the field lacks the `res_partner_many2one` widget. The user is forced to enter the English name instead.

## Solution ✅
Add the `res_partner_many2one` widget and the `res_partner_search_mode` context to the `Many2one` field in the XML view. This triggers Odoo's internal optimizations for partner searches and appropriately handles translated display names.

```xml
<field name="partner_id" widget="res_partner_many2one" context="{'res_partner_search_mode': 'customer', 'show_address': 1, 'show_vat': True}"/>
```

## ⚠️ Pitfalls
Using a generic `Many2one` field for `res.partner` without the proper context or widget might limit the search strictly to raw un-translated fields in certain edge cases, causing localization issues for users working strictly in Arabic.

## Odoo Versions
Odoo 16+
