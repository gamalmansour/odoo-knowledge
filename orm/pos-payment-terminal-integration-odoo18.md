# POS Electronic Payment Terminal Architecture in Odoo 18

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 18.0                                       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `point_of_sale`, `pos`, `payment_terminal`, `PaymentInterface`, `register_payment_method`, `pos.session`, `_load_pos_data_models`, `websocket`

---

## Problem

Migrating or creating custom electronic payment terminal integrations (e.g. Geidea, Six, Ingenico, PAX) in Odoo 18 causes crashes or silent failures:
1. Legacy AMD modules (`odoo.define`) and `point_of_sale.assets` in `__manifest__.py` fail to load.
2. Monkey-patching `PaymentScreen.prototype.addNewPaymentLine` breaks the OWL lifecycle, bypasses automatic payment validation (`config.auto_validate_terminal_payment`), and freezes the POS when errors or timeouts occur.
3. Custom terminal configuration models (e.g. `geidea.terminals`) are not loaded in the POS frontend store because `models.load_models` was removed.
4. Overriding `_load_pos_data_fields` on `pos.order` breaks POS totals and initialization.

---

## Root Cause

1. **Asset System:** In Odoo 18, POS assets must be declared under `'point_of_sale._assets_pos'` in `__manifest__.py`.
2. **Payment Architecture:** Odoo 18 uses ES modules and an explicit interface pattern:
   - Terminals must extend `PaymentInterface` from `@point_of_sale/app/payment/payment_interface`.
   - Registration is performed via `register_payment_method(key, Class)` from `@point_of_sale/app/store/pos_store`.
3. **Data Loading Mixin:** In Odoo 18, models loaded into POS must inherit `pos.load.mixin` and be appended to `pos.session._load_pos_data_models(config_id)`.
4. **Payment Method Fields:** `pos.payment.method` defines an explicit list in `_load_pos_data_fields`. Any custom fields (like the terminal profile `Many2one`) must be appended to `super()._load_pos_data_fields(config_id)`.

---

## Solution ✅

### 1. Backend: Terminal Profile & POS Data Loading

```python
# models/my_terminal.py
class MyTerminal(models.Model):
    _name = 'my.terminal'
    _inherit = ['pos.load.mixin']
    _description = 'Payment Terminal Profile'

    name = fields.Char(required=True)
    ip_address = fields.Char()
    port = fields.Integer(default=5000)

    @api.model
    def _load_pos_data_fields(self, config_id: int):
        return ['id', 'name', 'ip_address', 'port']


# models/pos_session.py
class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data_models(self, config_id: int):
        data = super()._load_pos_data_models(config_id)
        if 'my.terminal' not in data:
            data.append('my.terminal')
        return data


# models/pos_payment_method.py
class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [('my_terminal', 'My Terminal')]

    my_terminal_id = fields.Many2one('my.terminal', string='Terminal Profile')

    @api.model
    def _load_pos_data_fields(self, config_id: int):
        params = super()._load_pos_data_fields(config_id)
        params.append('my_terminal_id')
        return params
```

### 2. Frontend: Extend PaymentInterface

```javascript
// static/src/app/payment_my_terminal.js
import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class PaymentMyTerminal extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.pendingResolution = null;
    }

    async send_payment_request(uuid) {
        super.send_payment_request(...arguments);
        const line = this.pos.models["pos.payment"].getBy("uuid", uuid);
        line.set_payment_status("waitingCard");

        return new Promise((resolve) => {
            this.pendingResolution = resolve;
            // Initiate communication (WebSocket, HTTP, etc.)
            // Call this.pendingResolution(true) on success or (false) on failure
        });
    }

    async send_payment_cancel(order, uuid) {
        super.send_payment_cancel(...arguments);
        if (this.pendingResolution) {
            this.pendingResolution(false);
            this.pendingResolution = null;
        }
        return true;
    }

    close() {
        super.close(...arguments);
        if (this.pendingResolution) {
            this.pendingResolution(false);
            this.pendingResolution = null;
        }
    }
}
```

### 3. Registration

```javascript
// static/src/overrides/models/models.js
import { register_payment_method } from "@point_of_sale/app/store/pos_store";
import { PaymentMyTerminal } from "@my_module/app/payment_my_terminal";

register_payment_method("my_terminal", PaymentMyTerminal);
```

---

## ⚠️ Pitfalls

1. **Do NOT monkey-patch `PaymentScreen.prototype.addNewPaymentLine`**: This breaks standard POS order calculations and bypasses `PaymentScreen.sendPaymentRequest(line)`.
2. **WebSocket Timeouts and Errors**: Always bind `ws.onerror`, `ws.onclose`, and add a safety `setTimeout` so cashiers are never stuck with a frozen UI if the local terminal agent hangs.
3. **Do NOT override `_load_pos_data_fields` on `pos.order`**: See `orm/pos-config-load-pos-data-fields-pitfall.md`.
4. **Data Security & Privacy**: Never exfiltrate merchant company VAT, emails, or transaction figures to third-party endpoints.

---

## Verification

1. Open POS Session -> Open DevTools Console -> Ensure `register_payment_method` runs without errors.
2. Verify `pos.models["my.terminal"].getAll()` contains loaded terminals.
3. In Payment Screen, select the terminal payment method -> click Validate or let it auto-trigger -> verify payment line status changes to `waitingCard`, responds to terminal events, and transitions to `done`.
