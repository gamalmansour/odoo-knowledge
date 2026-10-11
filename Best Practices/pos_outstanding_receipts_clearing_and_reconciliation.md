# تسوية وتصفير حساب المقبوضات المعلقة (POS Outstanding Receipts Clearing & Reconciliation)

## 📌 Context
في أودو (خاصة V16 إلى V18)، عند إغلاق جلسات نقاط البيع (POS Sessions)، يقوم النظام بإنشاء قيود إقفال يومية تنشئ سطوراً مدينة في حساب المقبوضات المعلقة (`Outstanding Receipts` / `101003`). إذا لم يتم استيراد كشوفات الحسابات البنكية ومطابقتها دورياً، يتراكم هذا الحساب بمبالغ ضخمة وتظل مئات السطور مفتوحة دون تسوية.

## ⚠️ Pitfalls (المخاطر والعيوب الشائعة)
1. **الخلط بين رصيد ميزان المراجعة وحالة المطابقة (Reconciliation Status):**
   - عمل قيد يومية عام (`Miscellaneous Entry`) بالطرف الدائن لحساب المقبوضات المعلقة يُعدل الرصيد المالي في ميزان المراجعة والأستاذ العام، لكن **لا يقوم بتسوية السطور داخلياً (Internal Reconciliation)** إذا كان الحساب معلم كـ `reconcile=True`.
   - النتيجة: تظل مئات السطور القديمة تظهر في شاشات المطابقة وكشوف الحسابات كبنود معلقة مفتوحة (`reconciled = False`).
2. **استمرار تغذية الحساب من جلسات الـ POS الجديدة:**
   - تسوية الرصيد القديم لا تمنع الحساب من التراكم مجدداً طالما طرق الدفع (`pos.payment.method`) مربوطة افتراضياً على `Outstanding Receipts`.
3. **التسوية اليدوية الجماعية (Bulk Reconciliation Performance):**
   - مطابقة آلاف السطور دفعة واحدة عبر الواجهة قد تسبب مهلة انتهاء (Timeout) لـ RPC. يجب تنفيذ المطابقة برمجياً عبر الـ ORM في سكريبت نظيف.

## ✅ Solution (الحل المعتمد)

### 1. المطابقة البرمجية للسطور القديمة مع قيد التسوية:
```python
account = env['account.account'].search([('code', '=', '101003')], limit=1)

# جلب السطور المدينة القديمة
hist_lines = env['account.move.line'].search([
    ('account_id', '=', account.id),
    ('parent_state', '=', 'posted'),
    ('date', '<=', '2026-10-03'),
    ('reconciled', '=', False)
])

# جلب السطر الدائن لقيد التسوية
misc_line = env['account.move.line'].search([
    ('move_id.name', '=', 'MISC/2026/10/0001'),
    ('account_id', '=', account.id),
    ('credit', '>', 0),
    ('reconciled', '=', False)
], limit=1)

# تنفيذ المطابقة
if hist_lines and misc_line:
    (hist_lines | misc_line).reconcile()
```

### 2. منع التراكم عبر إعدادات الـ POS:
تخصيص حساب وسيط خاص بكل بنك/طريقة دفع (`Intermediary Account`) في إعدادات `pos.payment.method` بدلاً من الاعتماد على حساب موحد معلق.

## 🏷️ Metadata
- **Category:** Accounting
- **Tags:** `pos`, `accounting`, `reconciliation`, `outstanding-receipts`, `odoo18`
- **Odoo Versions:** 16.0, 17.0, 18.0
- **Last Verified:** 2026-10-04
