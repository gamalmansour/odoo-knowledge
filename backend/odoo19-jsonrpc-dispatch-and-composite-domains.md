# Odoo 19 JSON-RPC Dispatcher Param Extraction & Multi-Attribute Composite Domain Normalization

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo19`, `jsonrpc`, `dispatcher`, `domain`, `search`, `api`, `flutter`

---

## Problem

When building custom HTTP JSON-RPC controllers in Odoo 19 for mobile apps (e.g. Flutter) or web frontends, two critical issues occur:

1. **Parameter Unpacking Failure:**
   Attempting to read parameters via `request.params.get('key')` or `request.dispatcher.jsonrequest.get('key')` returns `None` or an empty dictionary, because `request.dispatcher.jsonrequest` in Odoo 19 encloses the whole payload `{"jsonrpc": "2.0", "method": "call", "params": {...}}`.

2. **Composite Polish-Notation Domain Crash:**
   When searching models with multiple conditional filters (e.g., category, price range, multiple styles, multiple materials), mixing implicit ANDs with nested OR clauses (`'|'`) directly causes an invalid domain syntax error or malformed SQL queries.

```python
# Fails in Odoo 19:
req = request.dispatcher.jsonrequest
category = req.get('category') # Returns None!

# Invalid domain structure:
domain = [('is_published', '=', True), '|', ('style', '=', 'modern'), ('style', '=', 'boho')] # Breaks with 3+ clauses!
```

## Root Cause

1. **Dispatcher Restructuring:** In Odoo 19, the HTTP JSON dispatcher stores the full JSON-RPC 2.0 envelope in `request.dispatcher.jsonrequest`. If client libraries send standard JSON-RPC packets, the parameters reside under the nested `'params'` key.
2. **Polish Prefix Domain Rules:** Odoo search domains strictly require prefix notation (`['|', clause1, clause2]`). Combining multiple multi-attribute OR groups with standard AND filters breaks without formal AST composition.

## Solution ✅

### 1. Robust Universal Parameter Extractor

Implement an extraction helper in your controller that inspects both top-level and nested `params`:

```python
def _extract_params(self) -> dict:
    """Safely extracts JSON-RPC 2.0 params across Odoo dispatcher variations."""
    json_req = getattr(request, 'params', None)
    if not json_req and hasattr(request, 'dispatcher'):
        json_req = getattr(request.dispatcher, 'jsonrequest', None)
    if isinstance(json_req, dict) and 'params' in json_req and isinstance(json_req['params'], dict):
        return json_req['params']
    if isinstance(json_req, dict):
        return json_req
    return {}
```

### 2. Normalized Composite Domain Construction

Use `Domain.and_()` (or `expression.AND`) to combine independent filter domains safely:

```python
from odoo.fields import Domain
# or from odoo.osv import expression

domains = [[('is_published', '=', True)]]

if category:
    domains.append([('furniture_category_id.code', '=', category)])

if min_price is not None:
    domains.append([('list_price', '>=', float(min_price))])

if max_price is not None:
    domains.append([('list_price', '<=', float(max_price))])

if selected_styles: # list of strings
    style_domain = [('furniture_style', '=', selected_styles[0])]
    for s in selected_styles[1:]:
        style_domain = ['|'] + style_domain + [('furniture_style', '=', s)]
    domains.append(style_domain)

final_domain = Domain.and_(domains)
products = request.env['product.template'].sudo().search(final_domain, order=order_clause)
```

## ⚠️ Pitfalls

- Never assume `request.params` has unpacked the JSON body. Always check both `params` and `request.dispatcher.jsonrequest`.
- In Odoo 19, `_sql_constraints` is deprecated. Use `@api.constrains('code')` with Python validation and `ValidationError`.
- When filtering text with multiple fields (name, description, material), wrap each OR group in its own sub-domain before merging with `Domain.and_`.

## Verification

Send a JSON-RPC 2.0 request via curl to verify:

```bash
curl -X POST http://127.0.0.1:8069/api/spacecraft/catalog \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "call", "params": {"category": "living_room", "min_price": 5000, "sort_by": "price_asc"}}'
```

Expected output: HTTP 200 with JSON response containing filtered products array and count.
