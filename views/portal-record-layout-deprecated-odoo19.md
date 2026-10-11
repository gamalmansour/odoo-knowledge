# portal_record_layout Deprecated in Odoo 19

## Problem
When migrating or building portal views in Odoo 19, using the `<t t-call="portal.portal_record_layout">` template will throw a 500 Internal Server Error: `Template not found: 'portal.portal_record_layout'`.

In older Odoo versions, this template was used to wrap record details with a standard header and body layout. It has been removed or restructured in newer versions.

## Solution
Instead of relying on the removed `portal_record_layout` template, use standard Bootstrap card classes directly within `<t t-call="portal.portal_layout">`. 

### Before (Odoo 16/17):
```xml
<t t-call="portal.portal_record_layout">
    <t t-set="card_header">
        <h5 class="mb-0">Record Title</h5>
    </t>
    <t t-set="card_body">
        <p>Record details...</p>
    </t>
</t>
```

### After (Odoo 19):
```xml
<div class="card mt-3">
    <div class="card-header">
        <h5 class="mb-0">Record Title</h5>
    </div>
    <div class="card-body">
        <p>Record details...</p>
    </div>
</div>
```

## Versions
Verified on Odoo 19.
