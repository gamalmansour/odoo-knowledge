# POS Order Validation Freeze on Company Customers (Automatic Invoice PDF Download)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | performance                                |
| Odoo Versions | 17, 18                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-17                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `pos`, `payment_screen`, `shouldDownloadInvoice`, `wkhtmltopdf`, `invoice`, `performance`, `ui-freeze`, `owl`

---

## Problem

When confirming/validating an order in Point of Sale (POS), the screen freezes with a loading spinner for 8 to 10+ seconds before transitioning to the Receipt Screen.
This issue prominently happens when selecting a customer with `company_type == 'company'`, or when the "Invoice" button is manually checked on the payment screen.

## Root Cause

1. In Odoo standard POS (`point_of_sale/static/src/app/models/pos_order.js`), selecting a customer whose `company_type == "company"` automatically forces the invoice flag on:
   ```javascript
   if (partner.company_type == "company") {
       this.set_to_invoice(true);
   }
   ```
2. During `PaymentScreen.validateOrder()`, Odoo wraps the validation in `ui.block()` and checks:
   ```javascript
   if (this.shouldDownloadInvoice() && this.currentOrder.is_to_invoice()) {
       if (this.currentOrder.raw.account_move) {
           await this.invoiceService.downloadPdf(this.currentOrder.raw.account_move);
       }
   }
   ```
3. By default, `shouldDownloadInvoice()` returns `true`.
4. On the backend, `invoiceService.downloadPdf()` triggers `account.move._render_qweb_pdf()`, executing `wkhtmltopdf` synchronously to generate an A4 invoice PDF and download it to the browser.
5. On many environments, `wkhtmltopdf` takes 7-10 seconds per invoice report, leaving the cashier staring at a frozen UI spinner on every corporate checkout.

## Solution ✅

### 1. Override `PaymentScreen.shouldDownloadInvoice()`

Odoo explicitly intended `shouldDownloadInvoice()` to be overridden by localizations/modules that do not want automatic synchronous PDF downloads on POS sales:

```javascript
// static/src/overrides/payment_screen.js
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(PaymentScreen.prototype, {
    /**
     * Prevent synchronous A4 invoice PDF generation and download
     * during order validation to eliminate cashier UI freezes.
     */
    shouldDownloadInvoice() {
        return false;
    },
});
```

### 2. Provide On-Demand Invoice Download on ReceiptScreen

Cashiers and customers who actually need the A4 tax invoice PDF can still download it with one click directly from the Receipt Screen or Ticket Screen:

```javascript
// static/src/overrides/receipt_screen.js
import { useService } from "@web/core/utils/hooks";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.accountMoveService = useService("account_move");
    },
    get hasInvoice() {
        return Boolean(this.currentOrder?.raw?.account_move);
    },
    async actionDownloadInvoice() {
        const moveId = this.currentOrder?.raw?.account_move;
        if (moveId) {
            await this.accountMoveService.downloadPdf(moveId);
        }
    },
});
```

```xml
<!-- static/src/overrides/receipt_screen.xml -->
<xpath expr="//div[hasclass('receipt-options')]/div[hasclass('d-flex')][1]" position="after">
    <button t-if="hasInvoice"
            class="btn btn-outline-secondary w-100 py-2 d-flex align-items-center justify-content-center gap-2 mt-1"
            t-on-click="() => this.actionDownloadInvoice()"
            title="تحميل الفاتورة الضريبية A4 PDF">
        <i class="fa fa-file-pdf-o text-danger fs-5"/>
        <span class="fw-bold">تحميل الفاتورة الضريبية (A4 PDF)</span>
    </button>
</xpath>
```

### 3. Ensure External API Calls (like WhatsApp Gateway) Are Asynchronous

If sending receipts via external HTTP gateways (e.g. UltraMsg), never make synchronous HTTP calls (`requests.post`) inside the POS order sync or RPC handler. Use a daemon `threading.Thread`:

```python
threading.Thread(
    target=self._send_whatsapp_background,
    args=(chat_url, chat_payload, image_url, image_payload),
    daemon=True,
).start()
```

## ⚠️ Pitfalls

- **Do NOT disable backend invoicing:** The order must still create the `account.move` journal entry and link `order.account_move`. Only disable the **automatic frontend PDF download**.
- **Always provide an on-demand fallback:** If automatic download is suppressed, make sure the cashier can still download the invoice via an explicit button on the Receipt Screen or Ticket Screen.

## Verification

1. Open POS, add products to cart.
2. Select a customer of type "Company" (e.g. `company_type = 'company'`).
3. Proceed to payment screen; observe the "Invoice" button is active.
4. Click **Validate**.
5. The screen transitions to Receipt Screen immediately (under 0.5s) with zero freeze.
6. The "تحميل الفاتورة الضريبية (A4 PDF)" button appears on Receipt Screen and downloads the invoice on demand when clicked.

## References

- `odoo/addons/point_of_sale/static/src/app/screens/payment_screen/payment_screen.js`
- Related file: `views/pos-receipt-screen-whatsapp-owl-patch.md`
