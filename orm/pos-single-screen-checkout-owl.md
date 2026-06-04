# POS Single-Screen Checkout (Quick Pay) in OWL

**Category:** Point of Sale (UI Customization)  
**Odoo Versions:** 17, 18  
**Tags:** `pos`, `owl`, `quick-checkout`, `payment`, `numpad`

## Goal
Combine the `ProductScreen` and `PaymentScreen` into a unified checkout interface (Single-Screen POS), allowing the cashier to select products, choose payment methods, enter partial amounts via the Numpad, and validate the order without navigating to a separate screen.

## Solution ✅
1. **XML Patch (`product_screen.xml`):**
   - Replace the `ActionpadWidget` (or its Payment button) with `<div class="paymentmethods">` containing buttons mapped from `pos.config.payment_method_ids`.
   - Add `<PaymentScreenPaymentLines />` under `<OrderSummary />` to display active payment lines.
   - Add a custom `Validate` button that binds to `validateOrder()`.

2. **JS Patch (`product_screen.js`):**
   - Inject `PaymentScreenPaymentLines` and `PaymentScreenStatus` into `ProductScreen.components`.
   - **Numpad Routing:** Override `onNumpadClick`. If `this.selectedPaymentLine` exists, route input to the payment line. Otherwise, call `super.onNumpadClick()` (for quantity/price).
   - **Buffer Hook:** Update the `numberBuffer.use` config in `setup()` to add `triggerAtInput` so that typed numbers update the payment line instantly.
   - **Port Methods:** Copy essential payment logic (`addNewPaymentLine`, `updateSelectedPaymentline`, `validateOrder`, `_isOrderValid`, `_finalizeValidation`, etc.) from `PaymentScreen` prototype into the `ProductScreen` patch.

## ⚠️ Pitfalls
- **Numpad Conflict:** By default, the Numpad on the ProductScreen is strictly for `qty`, `discount`, and `price`. If you inject payment features, you **must** intercept `onNumpadClick` and switch context based on whether the user selected a product line or a payment line.
- **`numberBuffer` Override:** Overriding `numberBuffer.use()` in `setup()` must still include `useWithBarcode: true` so the barcode scanner continues to work seamlessly on the main screen.
- **Terminal Integration:** If using external payment terminals (e.g., Ingenico), you must include the async terminal logic (`sendPaymentRequest`, `sendPaymentCancel`, etc.) or validation will break for credit cards.
