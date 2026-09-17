# Extending POS ReceiptScreen with WhatsApp Sharing via OWL Patch

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 17, 18                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-17                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `pos`, `owl`, `receipt-screen`, `whatsapp`, `patch`, `arabic-indic-digits`, `assets`

---

## Problem

When attempting to add external communication buttons (e.g. WhatsApp, SMS, or Telegram sharing) to the Point of Sale `ReceiptScreen` in Odoo 17/18:
1. The customer phone number input is hidden by default because `showPhoneInput()` returns `false` in core `ReceiptScreen`.
2. Phone numbers entered by cashiers in Arabic locales frequently contain Eastern Arabic-Indic numerals (`٠١٢٣٤٥٦٧٨٩`) or omit international country calling codes (e.g., Saudi `05...` instead of `9665...`), causing WhatsApp `api.whatsapp.com` links to fail silently or open with an invalid destination.
3. Injecting actions into the receipt screen requires targeting the specific action container (`div.sending-receipt-management`) rather than appending to outer layout blocks.

## Root Cause

1. In `point_of_sale.ReceiptScreen`:
   ```javascript
   showPhoneInput() {
       return false;
   }
   ```
   Without overriding this method, `<input t-if="showPhoneInput()" .../>` will never render.
2. In Arab markets (Saudi Arabia, Egypt, UAE), customers or cashiers frequently input phone numbers using localized device keyboards producing Unicode Eastern Arabic digits (`٠-٩`), which are rejected by international deep links like `api.whatsapp.com/send?phone=...`.

## Solution ✅

### 1. Patch `ReceiptScreen` in JavaScript (`static/src/overrides/receipt_screen.js`)

```javascript
import { patch } from "@web/core/utils/patch";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { _t } from "@web/core/l10n/translation";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        const partner = this.currentOrder?.get_partner();
        if (!this.state.phone && partner) {
            this.state.phone = partner.mobile || partner.phone || "";
        }
    },

    showPhoneInput() {
        return true;
    },

    cleanPhoneNumber(phone) {
        if (!phone) return "";
        // 1. Convert Eastern Arabic-Indic digits (٠-٩) to Western (0-9)
        const arabicIndicDigits = {
            '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
            '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
        };
        let clean = phone.replace(/[٠-٩]/g, (d) => arabicIndicDigits[d]);
        clean = clean.replace(/[^0-9]/g, "");

        // 2. Normalize local country formats
        if (clean.startsWith("05") && clean.length === 10) {
            clean = "966" + clean.slice(1);
        } else if (clean.startsWith("5") && clean.length === 9) {
            clean = "966" + clean;
        } else if (clean.startsWith("01") && clean.length === 11) {
            clean = "20" + clean.slice(1);
        } else if (clean.startsWith("00")) {
            clean = clean.slice(2);
        }
        return clean;
    },

    actionSendReceiptOnWhatsApp() {
        const rawPhone = this.state.phone;
        const cleanPhone = this.cleanPhoneNumber(rawPhone);
        if (!cleanPhone) {
            this.notification.add(_t("Please enter a valid customer phone number"), { type: "danger" });
            return;
        }
        const message = this.buildWhatsAppReceiptMessage();
        const url = `https://api.whatsapp.com/send?phone=${cleanPhone}&text=${encodeURIComponent(message)}`;
        window.open(url, "_blank");
    },
});
```

### 2. Extend the XML Template (`static/src/overrides/receipt_screen.xml`)

Target `div.sending-receipt-management`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates id="template" xml:space="preserve">
    <t t-name="whatsapp_sales_lite.ReceiptScreen" t-inherit="point_of_sale.ReceiptScreen" t-inherit-mode="extension">
        <xpath expr="//div[hasclass('sending-receipt-management')]" position="inside">
            <button class="btn btn-success h-100 d-flex align-items-center justify-content-center gap-1"
                    t-att-style="`width: ${this.ui.isSmall ? '4rem' : '8rem'}`"
                    t-on-click="() => this.actionSendReceiptOnWhatsApp()"
                    title="Send via WhatsApp">
                <i class="fa fa-whatsapp fa-lg"/>
                <span t-if="!this.ui.isSmall">WhatsApp</span>
            </button>
        </xpath>
    </t>
</templates>
```

### 3. Register POS Assets Bundle in `__manifest__.py`

```python
    'depends': ['point_of_sale'],
    'assets': {
        'point_of_sale._assets_pos': [
            'my_module/static/src/**/*',
        ],
    },
```

## ⚠️ Pitfalls

- **Manifest Asset Bundle:** In Odoo 17 and 18, POS assets are registered under `'point_of_sale._assets_pos'`, NOT `point_of_sale.assets`.
- **Server Cache:** When modifying `__manifest__.py` assets, restarting the server or running `./odoo-bin -u <module>` is required to re-bundle the assets.
- **Eastern Arabic Digits:** Always normalize `[٠-٩]` to ASCII digits `[0-9]` in JavaScript before constructing `wa.me` links.

## Verification

1. Start POS session in browser.
2. Complete an order to reach `ReceiptScreen`.
3. Verify that the customer phone input is visible and pre-filled with partner mobile/phone.
4. Click the green WhatsApp button and confirm the deep link opens with the correctly formatted international phone number and receipt body.
