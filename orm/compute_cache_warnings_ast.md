# Odoo 17 Compute Field Caching Issue

## Problem
In Odoo 17, when multiple fields share the same `compute="some_method"` method, they must have exactly the same parameters for `store` and `compute_sudo`. If one field has `store=True` and another has `store=False`, or if `compute_sudo=False` is set on one but omitted on the other, Odoo 17 will throw caching warnings and might result in unpredictable recalculations.

## Solution ✅
Ensure absolute consistency across all shared compute fields. When multiple fields compute from the same method:
- All fields should be `store=True` or all should be `store=False`.
- All fields should have `compute_sudo=False`.

**Automated AST Script:**
We have created a Python AST script (`fix_compute.py`) that scans the Odoo modules and automatically injects `store=True` and `compute_sudo=False` into the parameter list of all shared computed fields. 

## ⚠️ Pitfalls
Using regex replacement for this task can be dangerous because `fields.XXX` declarations often span multiple lines and contain nested parentheses or commas inside strings. Using Python's `ast` module to locate the node's line number and injecting the parameters programmatically is much safer.

## Odoo Versions
Verified on Odoo 17 Enterprise & Community.
