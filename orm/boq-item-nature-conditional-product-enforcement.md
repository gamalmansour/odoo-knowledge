# Multi-Level BOQ Item Nature and Conditional Product Enforcement

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `views`, `boq`, `item_nature`, `product_id`, `related-field`, `constrains`, `data-integrity`

---

## Problem

In construction tender/estimating modules, Bill of Quantities (BOQ) lines can represent either:
1. **Direct Supply / Off-the-shelf Item:** Directly mapped to a standard catalog product (e.g., standard PVC pipe, ready-mix concrete C30) where rate cards and historical purchase prices apply (`Suggest Price`).
2. **Composite Work Package:** A complex package (e.g., Substructure Excavation, HVAC Installation) whose cost is built bottom-up through nested breakdown items (materials, equipment, labor, subcontracts) and should **not** require a catalog product.

When refactoring a BOQ breakdown model (`tender.boq.breakdown`) to make `product_id` optional for composite packages, two major bugs occur:
1. **The Related Field Flush Trap:** The `name` or `uom_id` fields were defined as `related='product_id.name', store=True, readonly=False`. The moment a user creates a composite package with `product_id = False`, Odoo's related field engine triggers an inverse write and clears `name` to `False` (raising validation or user confusion).
2. **Leaf Node Bypass:** If `product_id` is made optional across the model, users might create Level 3 breakdown lines without products, which breaks downstream purchase requisitions, CBS cost codes, and historical rate lookups.

```python
# Symptom: Manual package name entered by the user gets silently overwritten with False
rec.write({'item_nature': 'composite', 'name': 'Excavation Works', 'product_id': False})
# Result: rec.name becomes False!
```

---

## Root Cause

1. In Odoo, when a field is declared with `related='product_id.name'`, unsetting `product_id` causes the related field mechanism to evaluate `False.name -> False` and store `False` in the database, overriding whatever string was passed in `vals`.
2. A single model (`tender.boq.breakdown`) is often reused for both **Level 2** (`parent_id = False`) and **Level 3** (`parent_id != False`). Making `product_id` optional at the model level (`required=False`) without tiered constraints allows leaves to be created without products.

---

## Solution ✅

### 1. Replace `related=` with Stored Compute + Readonly=False
Convert `name` and `uom_id` from `related` fields into stored computed fields that populate from `product_id` as a default, but respect manual user input:

```python
name = fields.Char(
    string="Description",
    compute="_compute_name",
    store=True,
    readonly=False,
    required=True,
)
uom_id = fields.Many2one(
    "uom.uom",
    string="Unit of Measure",
    compute="_compute_uom_id",
    store=True,
    readonly=False,
    required=True,
)

@api.depends("product_id")
def _compute_name(self) -> None:
    for rec in self:
        if rec.product_id and not rec.name:
            rec.name = rec.product_id.name or rec.product_id.display_name
        elif not rec.name:
            rec.name = ""

@api.depends("product_id")
def _compute_uom_id(self) -> None:
    for rec in self:
        if rec.product_id and not rec.uom_id:
            rec.uom_id = rec.product_id.uom_id
```

### 2. Tiered Python Constraints (`@api.constrains`)
Enforce `product_id` conditionally based on the item level and nature:
- **Level 1 (`tender.boq.line`):** If `item_nature == 'direct'`, `product_id` is required.
- **Level 2 (`parent_id == False`):** If `item_nature == 'direct'`, `product_id` is required. If `composite`, optional.
- **Level 3 (`parent_id != False`):** Strictly **always required** (leaf costing elements).

```python
@api.constrains("item_nature", "product_id", "parent_id")
def _check_breakdown_product_requirement(self) -> None:
    for rec in self:
        # Level 3 items MUST have a product
        if rec.parent_id and not rec.product_id:
            raise ValidationError(
                _("Sub-item (Level 3) '%s' must have a Product specified for accurate unit costing.", rec.name)
            )
        # Level 2 Direct items MUST have a product
        if not rec.parent_id and rec.item_nature == "direct" and not rec.product_id:
            raise ValidationError(
                _("Direct Item '%s' must have a Product selected.", rec.name)
            )
```

### 3. Responsive XML Views with Context Banners
Add dynamic `required` and `invisible` attributes in the XML list/tree views, along with contextual guidance for estimators:

```xml
<!-- In tender_opportunity_views.xml or breakdown views -->
<div class="alert alert-info d-flex align-items-center mb-3" role="alert">
    <i class="fa fa-info-circle fa-2x me-3 text-info"/>
    <div>
        <strong>BOQ Item Nature &amp; Pricing Guidance:</strong><br/>
        • <strong>Composite Work Packages:</strong> Leave <em>Product</em> empty if this line is broken down into sub-components.<br/>
        • <strong>Direct Supply:</strong> Select a standard <em>Product</em> to enable instant rate-card pricing via <strong>Suggest Price 🪄</strong>.
    </div>
</div>

<field name="item_nature" widget="badge"
       decoration-info="item_nature == 'composite'"
       decoration-success="item_nature == 'direct'"
       invisible="parent_id != False"/>

<field name="product_id"
       required="parent_id != False or (item_nature == 'direct' and not display_type)"/>
```

---

## ⚠️ Pitfalls

1. **`readonly=False` on computed fields:** Without `readonly=False`, users will be unable to type custom package descriptions or adjust units of measure in form/list views.
2. **Display Type Lines (Sections & Notes):** In BOQ models using `display_type` for section headers and notes, always add `and not display_type` to both the Python constraint and XML `required` expression. Otherwise, section headers will trigger validation errors for missing products.
3. **Existing Stored Data:** When changing `related=` to computed, ensure default empty strings (`""`) rather than `False` to prevent UI serialization warnings.

---

## Verification

Run test cases verifying:
1. Level 1 Direct without product -> ValidationError.
2. Level 1 Composite without product -> Created successfully.
3. Level 2 Direct without product -> ValidationError.
4. Level 2 Composite without product -> Created successfully with custom name preserved.
5. Level 3 without product -> ValidationError.
6. Level 3 with product -> Created successfully.

---

## References

- Related file: `orm/boq-three-level-breakdown-domain-actions.md`
- Module implementation: `construction_tender/models/tender_boq_breakdown.py`
