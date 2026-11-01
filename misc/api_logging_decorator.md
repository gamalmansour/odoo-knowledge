# API Request Logging via Decorator

**Severity:** 🟡 Medium

**Date Added:** 2026-05-24  
**Last Verified:** 2026-05-24  
**Odoo Versions:** 16.0, 17.0, 18.0, 19.0  
**Tags:** API, Logging, Decorator, Security

## 📝 Problem Statement
We need to log all API requests for a specific Odoo controller to track endpoints hit, request payloads (JSON), and response data. Modifying each route method manually is tedious, error-prone, and violates DRY principles, especially when having dozens of endpoints. Furthermore, standard transactions rollback on failures, causing the logs of the errors themselves to be lost.

## ✅ Solution
Use a Python decorator in the controller to wrap the `http.route` methods.
To make it professional:
1. **Isolated Database Transaction:** Write logs using a separate database cursor (`registry(db_name).cursor()`) with a `commit()` so that error tracebacks are preserved even if the main Odoo transaction rolls back.
2. **Recursive Masking:** Recursively sanitize sensitive keys (like `password`) inside the payload before logging.
3. **Auto-Wrapping Loop:** Dynamically wrap all class route methods at module import time, preserving Odoo routing definitions.

### Implementation Steps

1. **Create the Logging Model (`mobile_api_log.py`)**
```python
from odoo import models, fields, api

class MobileApiLog(models.Model):
    _name = "mobile.api.log"
    _description = "Mobile API Log"
    _order = "create_date desc"

    name = fields.Char(string="Endpoint", required=True, readonly=True)
    request_data = fields.Text(string="Request JSON Payload", readonly=True)
    response_data = fields.Text(string="Response JSON Payload", readonly=True)
    state = fields.Selection([("success", "Success"), ("error", "Error")], string="Status", readonly=True)

    @api.model
    def action_cleanup_logs(self) -> None:
        """Deletes logs older than 30 days to prevent db bloat."""
        limit_date = fields.Datetime.subtract(fields.Datetime.now(), days=30)
        self.search([("create_date", "<", limit_date)]).unlink()
```

2. **Define the Decorator & Sanitizer in `controllers.py`**
```python
import functools
import json
import logging
import traceback
from odoo import registry
from odoo.http import request

_logger = logging.getLogger(__name__)

def sanitize_payload(payload):
    """Recursively mask sensitive keys like 'password' in dict structures."""
    if not isinstance(payload, dict):
        return payload
    sanitized = {}
    for k, v in payload.items():
        if k == 'password':
            sanitized[k] = '********'
        elif isinstance(v, dict):
            sanitized[k] = sanitize_payload(v)
        elif isinstance(v, list):
            sanitized[k] = [sanitize_payload(item) if isinstance(item, dict) else item for item in v]
        else:
            sanitized[k] = v
    return sanitized

def log_api_request(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        payload = {}
        if hasattr(request, 'jsonrequest'):
            payload = request.jsonrequest
        else:
            payload = kwargs
            
        payload_str = json.dumps(sanitize_payload(payload), indent=4, ensure_ascii=False)
        endpoint = request.httprequest.path

        response_str = ""
        state = 'success'

        try:
            response = func(self, *args, **kwargs)
            if isinstance(response, dict):
                response_str = json.dumps(response, indent=4, ensure_ascii=False)
            elif hasattr(response, 'data'):
                response_str = response.data.decode('utf-8')
            else:
                response_str = str(response)
        except Exception as e:
            state = 'error'
            response_str = traceback.format_exc()
            _logger.error(f"API Error at {endpoint}: {e}")
            raise
        finally:
            try:
                # Use separate database connection cursor to persist log on rollback
                db_name = request.session.db or request.db
                if db_name:
                    with registry(db_name).cursor() as new_cr:
                        new_env = request.env(cr=new_cr)
                        new_env['mobile.api.log'].sudo().create({
                            'name': endpoint,
                            'request_data': payload_str,
                            'response_data': response_str,
                            'state': state
                        })
                        new_cr.commit()
            except Exception as log_e:
                _logger.error(f"Failed to log API request: {log_e}")
                
        return response

    # Copy routing details for Odoo route registry scanning
    if hasattr(func, 'original_routing'):
        wrapper.original_routing = func.original_routing
    if hasattr(func, 'original_endpoint'):
        wrapper.original_endpoint = func.original_endpoint
    if hasattr(func, 'routing'):
        wrapper.routing = func.routing
    return wrapper
```

3. **Auto-Apply to All Route Methods**
Instead of decorating 50+ methods manually, append this to the bottom of `controllers.py` (after the class definition):
```python
# Auto-apply log decorator to all route handlers of the controller
for attr_name in dir(ConnectOdooToMobile):
    attr = getattr(ConnectOdooToMobile, attr_name)
    if callable(attr) and hasattr(attr, 'original_routing'):
        setattr(ConnectOdooToMobile, attr_name, log_api_request(attr))
```

## ⚠️ Pitfalls
1. **Public Routes vs Auth:** Always use `.sudo()` when creating the log record, as the API might be called by public users who lack write access to the log model.
2. **Missing `jsonrequest`:** For non-JSON routes (`type='http'`), `request.jsonrequest` will not exist. Always fallback to `kwargs` to prevent `AttributeError`.
3. **Transaction Rollbacks:** Standard logging inside `request.env` gets rolled back if the handler fails. **Always** use a cloned cursor (`with registry(db_name).cursor() as new_cr`) to force-commit error logs.
4. **Endpoint Redirection / Routing Attribute:** Odoo scans class attributes for `original_routing` during the module import definition before registering routes. If the wrapper does not copy `func.original_routing` to `wrapper.original_routing` and check `hasattr(attr, 'original_routing')` in the loop (since `routing` is resolved dynamically later), Odoo will skip route discovery entirely!

## 🔗 Related Resources
- Odoo HTTP Request Documentation
