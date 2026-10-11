---
tags: [frontend, pos, javascript, import, rpcerror]
versions: [18]
---

# POS JS Missing RPCError Import

## 🚨 Problem

When extending or patching POS screens (e.g., `PaymentScreen`), you might encounter a runtime error during payment validation:
```javascript
ReferenceError: RPCError is not defined
```
This happens when you try to catch `RPCError` in a `try...catch` block (e.g., inside `_finalizeValidation`) but forget to import it at the top of the file. A common mistake is importing only `ConnectionLostError` and forgetting `RPCError` and its handler `handleRPCError`.

## 💡 Solution

Ensure that both `RPCError` and `handleRPCError` are properly imported in your custom JS patch file.

### Incorrect
```javascript
import { ConnectionLostError } from "@web/core/network/rpc";
```

### Correct
```javascript
import { ConnectionLostError, RPCError } from "@web/core/network/rpc";
import { handleRPCError } from "@point_of_sale/app/errors/error_handlers";
```

## ⚠️ Pitfalls
- Just copying `try...catch` blocks from Odoo core POS files without bringing their respective imports to the top of your custom JS patch.
- Odoo's bundler might not warn you about missing imports during build time, leading to silent failures that only manifest during runtime when the catch block executes (e.g., during network issues or POS validation).

## Last Verified
2026-07-04
