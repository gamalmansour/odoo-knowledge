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
4. Each order opens a brand-new browser tab when using `window.open(url, "_blank")`, forcing WhatsApp Web to reconnect and re-sync on every order, causing extreme cashier lag and tab clutter.
5. WhatsApp Web URL parameters (`api.whatsapp.com` or `web.whatsapp.com`) do NOT support file or image attachments due to browser security restrictions, making direct receipt image attachment via URL impossible.
6. In Odoo 18, `pos.order` on the frontend frequently lacks the backend-generated `access_token`, resulting in empty or broken `{receipt_url}` electronic ticket links.

## Root Cause

1. In `point_of_sale.ReceiptScreen`:
   ```javascript
   showPhoneInput() {
       return false;
   }
   ```
   Without overriding this method, `<input t-if="showPhoneInput()" .../>` will never render.
2. In Arab markets (Saudi Arabia, Egypt, UAE), customers or cashiers frequently input phone numbers using localized device keyboards producing Unicode Eastern Arabic digits (`٠-٩`), which are rejected by international deep links like `api.whatsapp.com/send?phone=...`.
3. Using `_blank` as the window target in `window.open()` instructs the browser to always create an isolated tab, rather than reusing an existing WhatsApp Web tab.
4. Meta's web URL scheme only permits text payloads (`?text=...`). Sending actual image files requires either third-party WhatsApp Cloud APIs or client-side clipboard integration.
5. In Odoo 18, `access_token` is generated on the server during order sync and not mirrored back immediately into client memory.

## Solution ✅

### 1. Enhanced `ReceiptScreen` Patch (`static/src/overrides/receipt_screen.js`)

```javascript
import { patch } from "@web/core/utils/patch";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
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

    async actionSendReceiptOnWhatsApp() {
        const rawPhone = this.state.phone;
        const cleanPhone = this.cleanPhoneNumber(rawPhone);
        if (!cleanPhone) {
            this.notification.add(_t("Please enter a valid customer phone number"), { type: "danger" });
            return;
        }

        // 1. Guaranteed server access_token resolution for electronic receipt
        let accessToken = this.currentOrder?.access_token;
        if (!accessToken && this.currentOrder?.id) {
            try {
                const [orderData] = await this.pos.data.read("pos.order", [this.currentOrder.id], ["access_token"]);
                if (orderData?.access_token) {
                    accessToken = orderData.access_token;
                }
            } catch (err) {
                console.warn("[WhatsApp] Could not fetch server access_token:", err);
            }
        }

        // 2. Auto-copy thermal receipt image to clipboard (Instant Cmd+V)
        if (this.pos.config.whatsapp_auto_copy_receipt !== false) {
            try {
                const canvas = await this.renderer.toCanvas(OrderReceipt, {
                    data: this.pos.get_order().export_for_printing(),
                });
                canvas.toBlob(async (blob) => {
                    if (blob && navigator.clipboard?.write) {
                        await navigator.clipboard.write([
                            new ClipboardItem({ "image/png": blob }),
                        ]);
                        this.notification.add(
                            _t("Receipt image copied to clipboard! Press Ctrl+V in WhatsApp to attach it."),
                            { type: "info" }
                        );
                    }
                }, "image/png");
            } catch (e) {
                console.warn("[WhatsApp] Clipboard copy failed:", e);
            }
        }

        // 3. Single-Tab Reuse + Direct URL Scheme
        const message = await this.buildWhatsAppReceiptMessage(accessToken);
        const encodedText = encodeURIComponent(message);
        const clientType = this.pos.config.whatsapp_client_type || "web";

        let url = "";
        if (clientType === "desktop") {
            url = `whatsapp://send?phone=${cleanPhone}&text=${encodedText}`;
        } else {
            // Bypass api.whatsapp.com redirect delay
            url = `https://web.whatsapp.com/send?phone=${cleanPhone}&text=${encodedText}`;
        }

        // Reuse existing tab named "whatsapp_pos_window" to prevent tab explosion
        window.open(url, "whatsapp_pos_window");
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

### 3. Add POS Configuration Settings (`models/pos_config.py` & `models/res_config_settings.py`)

### 4. Dual Delivery Mode: Browser Flow vs. UltraMsg Server Gateway

In high-volume POS environments where cashiers cannot afford any browser window switching, or when browsers isolate WhatsApp Web via `Cross-Origin-Opener-Policy` (COOP):
1. **Option 1 (Browser / Desktop):** Manual client-side deep link with clipboard image copy.
2. **Option 2 (UltraMsg Server Gateway):** Zero-click automated server-side dispatch.
   - On payment validation (`onMounted` hook in `ReceiptScreen`), the frontend converts the receipt canvas to Base64 and invokes `action_send_whatsapp_gateway(phone, ticket_image)` on `pos.order`.
   - The backend dispatches the formatted text message and uploads the ticket PNG directly via UltraMsg API endpoints (`/messages/chat` and `/messages/image`).
   - Zero tabs opened, zero cashier distraction.

```javascript
// Automatic Gateway Dispatch in onMounted:
async actionSendReceiptViaGateway(isAuto = false) {
    const rawPhone = this.state.phone;
    const cleanPhone = this.cleanPhoneNumber(rawPhone);
    if (!cleanPhone) return;

    let ticketImageBase64 = false;
    if (this.pos.config.whatsapp_gateway_send_image !== false) {
        try {
            const canvas = await this.renderer.toCanvas(OrderReceipt, {
                data: this.pos.get_order().export_for_printing(),
            });
            ticketImageBase64 = canvas.toDataURL("image/png");
        } catch (e) {
            console.warn("[WhatsApp Gateway] Canvas render failed:", e);
        }
    }

    const orderId = this.currentOrder?.id;
    if (orderId) {
        await this.pos.data.call("pos.order", "action_send_whatsapp_gateway", [
            [orderId],
            cleanPhone,
            ticketImageBase64
        ]);
        this.notification.add(_t("Receipt sent via WhatsApp successfully!"), { type: "success" });
    }
}
```

## ⚠️ Pitfalls

- **WhatsApp Web COOP Multi-Tab Trap:** WhatsApp Web sets `Cross-Origin-Opener-Policy: same-origin`. This policy causes modern Chrome/Edge to isolate the opened WhatsApp tab, breaking JavaScript cross-window communication across subsequent orders. While window naming mitigates this, the definitive zero-tab solution is server-side gateway dispatch (UltraMsg).
- **Clipboard API Activation Loss:** Calling `navigator.clipboard.write` inside an asynchronous callback (e.g., inside `canvas.toBlob(...)`) can fail with a `NotAllowedError` because browser user activation expires. Resolve this by passing a `Promise<Blob>` directly into `new ClipboardItem({ "image/png": blobPromise })` and awaiting the clipboard write before opening windows.
- **`api.whatsapp.com` Redirect Penalty:** `api.whatsapp.com/send` performs an intermediate server redirect which introduces a 1-3 second delay. Use `https://web.whatsapp.com/send` directly for web.
- **Image URL Inability:** WhatsApp web scheme rejects image attachment parameters. Either use client-side clipboard copy or automated server gateway API dispatch.
- **Localhost Link Trap:** If POS runs locally or on internal IP (`192.168.x.x`), `{receipt_url}` sent to customers' phones will fail. Provide a `whatsapp_base_url` setting on `pos.config` (e.g., `https://pos.company.com`).
- **Server Cache:** When modifying `__manifest__.py` assets, restarting the server or running `./odoo-bin -u <module>` is required to re-bundle the assets.
- **Eastern Arabic Digits:** Always normalize `[٠-٩]` to ASCII digits `[0-9]` in JavaScript before constructing `wa.me` links or sending to gateway APIs.
- **UltraMsg /instance/status Nested Dictionary:** The `/instance/status` endpoint returns a nested structure `{"status": {"accountStatus": {"status": "authenticated", "substatus": "connected"}}}` rather than a flat string. Parsers must unwrap `accountStatus` to avoid false positive error notifications.
- **Synced Order `partner_id` Integer Trap (Odoo 18):** In Odoo 18, after order validation/sync, `pos.order` relational fields (`partner_id`) are loaded with `load=False`, returning raw integer IDs (e.g., `3`) instead of model records. Calling `order.get_partner()` yields an integer, causing `partner.mobile` and `partner.phone` to evaluate to `undefined`. A robust patch must resolve IDs through `pos.models["res.partner"]?.get(id)`.
- **Arab Region `phone` vs `mobile` Discrepancy:** Standard Odoo 18 `ReceiptScreen` only checks `partner?.mobile || ""`. In Egypt and Saudi Arabia, customer numbers are almost universally stored in `partner.phone` (with `mobile` being `False`). Always fall back to `partner.mobile || partner.phone || ""`.
- **Finalized Order `assert_editable()` Trap:** Calling `order.set_partner(partner)` on `ReceiptScreen` throws `Error: Finalized Order cannot be modified` because `order.finalized` is `true`. When changing or selecting a customer on `ReceiptScreen`, directly assign `order.partner_id = partner` in JS and call `pos.data.write("pos.order", [order.id], { partner_id: partner.id })` for server persistence.
- **UltraMsg `/messages/image` Asynchronous Failure Trap:** In UltraMsg, posting base64 data to `/messages/image` is accepted with HTTP 200, but fails asynchronously inside UltraMsg's worker with `status: unsent, failed_reason: error`, causing complete delivery failure. In contrast, `/messages/chat` (text) delivers with 100% reliability and zero failure rate. Therefore, UltraMsg gateway dispatch should always use `/messages/chat` delivering the formatted electronic ticket breakdown and direct validation link.
- **Duplicate Send Prevention (Auto-Send + Cashier Click):** When auto-send on screen mount is enabled (`onMounted`), cashiers often instinctively click the WhatsApp button on the receipt screen, causing a duplicate message to be delivered. Prevent this via a two-layer safeguard:
  1. **Frontend (OWL):** Track `this.state.whatsappSent` and `this._lastSentPhone`. If the cashier clicks the button again without changing the phone number, intercept it with an informational toast notification (`تم إرسال الفاتورة لهذا الرقم بالفعل`) and do not invoke the backend.
  2. **Backend (Python):** Maintain an in-memory 30-second debounce dictionary on `PosOrder._recent_gateway_dispatches` to safely ignore duplicate calls for the same order unless explicitly forced with a different destination.


## Verification

1. Start POS session in browser.
2. Select a customer whose phone is stored in `phone` field.
3. Validate order: verify the phone input on `ReceiptScreen` is automatically populated with the customer's phone.
4. For orders without a customer (walk-in): click **"اختيار عميل"**, select a customer from `PartnerList`: verify customer name updates, order updates, and phone fills immediately.
5. In Settings, test switching between **Browser** and **UltraMsg Gateway**.
6. For **UltraMsg Gateway**, click **Test Connection** to verify API credentials and instance status.
7. Complete a sale: verify message and receipt PNG arrive automatically on the customer's phone without opening any browser tabs.
8. For **Browser**, verify clipboard image copy and tab navigation.

