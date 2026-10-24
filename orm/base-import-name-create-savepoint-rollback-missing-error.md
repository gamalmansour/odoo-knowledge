# Excel Import "Create New Values" Fails with Cascading `Record does not exist or has been deleted` When a Custom Constraint Rejects Auto-Created Partners

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `base_import`, `name_create`, `savepoint`, `MissingError`, `Record does not exist or has been deleted`, `import_file`, `res.partner`, `account.move`, `constrains`

---

## Problem

> When importing records (e.g. `account.move` invoices or `sale.order`) via Excel/CSV with **"Create new values"** (`name_create_enabled_fields`) selected for relational fields (`partner_id`, `product_id`), a single custom `@api.constrains` failure on the parent model (such as requiring `partner_id.valid_customer == True`) triggers a cascade of misleading `MissingError` messages for every newly created partner and product across the entire sheet:

```
The file contains blocking errors (see below)
Customer 'cartona' is not verified as a Valid Customer. Invoices and Credit Notes can only be issued for validated customers. at multiple rows
Record does not exist or has been deleted. (Record: res.partner(8204,), User: 2) at multiple rows
Record does not exist or has been deleted. (Record: product.product(389,), User: 2) at multiple rows
Record does not exist or has been deleted. (Record: product.product(390,), User: 2) at multiple rows
```

## Root Cause

In `odoo/orm/models.py` (`Model.load()`):
1. `savepoint = cr.savepoint()` is created at the very start of `load()` **before** `_convert_records()` runs.
2. During `_convert_records()`, `ir.fields._str_to_many2one()` calls `RelatedModel.name_create(name=value)` for any missing relational value (`res.partner`, `product.product`) and stores the newly generated integer IDs into `data_list`.
3. Because `name_create()` only passes `{self._rec_name: name}`, custom approval booleans (such as `valid_customer = False` by default) remain `False` on the newly created partner.
4. During `flush()`, batch creation (`self._load_records(data_list)`) fails on the custom constraint (`ValidationError`), and `load()` falls back to a record-by-record loop.
5. On the first failing record in the loop, `savepoint.rollback()` rolls back the transaction all the way to the top of `load()` — **wiping out all records created by `name_create()` during `_convert_records()`** while `data_list` still holds their integer IDs (`8204`, `389`, etc.). Subsequent iterations in the retry loop then fail with `Record does not exist or has been deleted`.

## Solution ✅

Handle `import_file` context and `name_create()` in two complementary places:

1. **In `res.partner.name_create()` and `create()`:** Auto-populate `valid_customer` / `valid_vendor` based on context (`import_file`, `default_move_type`, `res_partner_search_mode`).
2. **In the `@api.constrains` methods on `account.move` / `sale.order`:** When `self.env.context.get('import_file')` is `True`, auto-promote unvalidated partners (`partner_id.sudo().valid_customer = True`) instead of raising `ValidationError`, covering both newly created and pre-existing unvalidated partners.

```python
@api.model
def name_create(self, name: str) -> tuple[int, str]:
    ctx = self.env.context
    extra_ctx = {}
    move_type = ctx.get('default_move_type')
    search_mode = ctx.get('res_partner_search_mode')
    is_purchase_ctx = (
        move_type in ('in_invoice', 'in_refund', 'in_receipt')
        or search_mode == 'supplier'
    )
    if ctx.get('import_file') or is_purchase_ctx or move_type in ('out_invoice', 'out_refund', 'out_receipt') or search_mode == 'customer':
        if is_purchase_ctx and 'default_valid_vendor' not in ctx:
            extra_ctx['default_valid_vendor'] = True
        elif 'default_valid_customer' not in ctx:
            extra_ctx['default_valid_customer'] = True
    if extra_ctx:
        self = self.with_context(**extra_ctx)
    return super().name_create(name)
```

And inside the constraint:
```python
@api.constrains('partner_id', 'move_type')
def _check_valid_account_move_partner(self) -> None:
    is_import = bool(self.env.context.get('import_file'))
    for move in self:
        if move.is_sale_document(include_receipts=True) and move.partner_id and not move.partner_id.valid_customer:
            if is_import:
                move.partner_id.sudo().valid_customer = True
                continue
            raise ValidationError(_("Customer '%(partner)s' is not verified as a Valid Customer.", partner=move.partner_id.display_name))
```

## ⚠️ Pitfalls

- **Only fixing `name_create()` is not enough:** If an Excel sheet references a partner that already exists in `res.partner` with `valid_customer = False` (e.g. a partner previously created as a vendor), `name_search()` finds it without calling `name_create()`, and the constraint will still fail and roll back the batch savepoint unless the constraint itself handles `import_file=True`.
- **Use `.sudo()` when auto-validating inside the constraint:** An accountant importing invoices may have `account.move` create rights without full `res.partner` write access.

## Verification

```bash
./odoo-bin -c custom.conf -d pure_integrated -u sale_visit --test-enable --test-tags /sale_visit:TestValidCustomerVendor --stop-after-init
```
