---
name: "Product Import Gotchas: Type, is_storable, and Duplicate Barcodes (Odoo 19)"
description: "Handles ValueError on product.template.type for storable products and ValidationError for duplicate barcodes."
---

# Product Import Gotchas in Odoo 19

## Context
When importing product masters from Excel/CSV into `product.template` in Odoo 19, you might run into two major issues:
1. `ValueError: Wrong value for product.template.type: 'product'`
2. `odoo.exceptions.ValidationError: Barcode(s) already assigned`

## ⚠️ Pitfalls

1. **`type` Field Deprecation for Storables**: In older Odoo versions, `type = 'product'` meant "Storable Product". In Odoo 18/19, `type` only accepts `consu` (Goods), `service` (Service), or `combo`. Storable products are now `type = 'consu'` with `is_storable = True`.
2. **Duplicate Barcodes in Raw Data**: Client-provided Excel files often contain copy-paste errors with duplicate barcodes. Odoo enforces strict global uniqueness on `barcode`. If your import script doesn't handle this, the entire batch will fail.

## Solution ✅

### 1. Handling Product Type and `is_storable`
When parsing the product type from Excel, check for the `is_storable` field dynamically and map "Storable" to `consu` + `is_storable=True`:

```python
ptype_str = str(row.get('Product Type')).lower()
ptype = 'consu'
is_storable = False

if 'storable' in ptype_str or 'good' in ptype_str or 'product' in ptype_str:
    is_storable = True
elif 'service' in ptype_str:
    ptype = 'service'

vals = {
    'type': ptype,
}
if 'is_storable' in env['product.template']._fields:
    vals['is_storable'] = is_storable
```

### 2. Handling Duplicate Barcodes
Before assigning a barcode from the Excel sheet, query the database to ensure it's not already assigned to *another* product:

```python
barcode = str(row.get('Barcode / باركود')).strip()

if barcode:
    # Check if this barcode is already used by another product
    existing_barcode = env['product.template'].search([
        ('barcode', '=', barcode), 
        ('id', '!=', prod.id if prod else 0)
    ], limit=1)
    
    if existing_barcode:
        print(f"Warning: Barcode {barcode} already exists on {existing_barcode.name}. Skipping barcode.")
        barcode = ""  # Clear the barcode so the record can still be created

if barcode:
    vals['barcode'] = barcode
```

## Odoo Versions
- Verified on Odoo 19.0.

*Last Verified: 2026-07-01*
