# Time Off Dashboard: Display Hour-based Leave Balances in Minutes Without Altering Leave Type Records

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr_holidays`, `time_off`, `dashboard`, `minutes`, `hours`, `owl`, `qweb`, `TimeOffCard`

---

## Problem

> A business requirement asks for leave balances configured in hours (`request_unit = 'hour'`) to be displayed in **minutes** exclusively on the Employee Time Off Dashboard (`hr_holidays.hr_leave_employee_view_dashboard`), without modifying the underlying `hr.leave.type` definition or existing allocations/leaves in the database.

Modifying `request_unit` in the database or modifying core calculations in `_get_consumed_leaves` causes critical regressions across leave validation, duration constraints, and payroll work entries.

## Root Cause

1. The Time Off Dashboard card (`TimeOffCard`) receives allocation data directly via the RPC call `hr.employee.get_time_off_dashboard_data`.
2. The QWeb template `hr_holidays.TimeOffCard` hardcodes unit labels (`<t t-if="data.request_unit == 'hour'" name="duration_unit">hours</t><t t-else="">days</t>`).
3. Simply multiplying values in Python or setting a custom unit without extending the OWL QWeb templates causes the template to fall back to `days` or display misleading unit names.

## Solution ✅

> Combine a safe Python override of `get_time_off_dashboard_data` with OWL QWeb template extensions (`t-inherit-mode="extension"`).

### 1. Python Logic (`hr.employee`)

Scale only the transient dictionary payload returned to the frontend dashboard. Clean floating-point inaccuracies:

```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @staticmethod
    def _convert_hours_to_minutes(hours: float | int | None) -> float | int:
        if not hours or not isinstance(hours, (int, float)):
            return 0
        minutes = hours * 60
        rounded = round(minutes, 2)
        if isinstance(rounded, float) and rounded.is_integer():
            return int(rounded)
        return rounded

    @api.model
    def get_time_off_dashboard_data(self, target_date: str | None = None) -> dict:
        dashboard_data = super().get_time_off_dashboard_data(target_date=target_date)
        duration_keys = (
            'remaining_leaves',
            'virtual_remaining_leaves',
            'max_leaves',
            'accrual_bonus',
            'leaves_taken',
            'virtual_leaves_taken',
            'leaves_requested',
            'leaves_approved',
            'closest_allocation_remaining',
            'closest_allocation_duration',
            'total_virtual_excess',
            'exceeding_duration',
            'max_allowed_negative',
        )
        for holiday in dashboard_data.get('allocation_data', []):
            data = holiday[1]
            if data.get('request_unit') == 'hour':
                data['request_unit'] = 'minute'
                data['display_as_minutes'] = True
                for key in duration_keys:
                    if key in data and isinstance(data[key], (int, float)):
                        data[key] = self._convert_hours_to_minutes(data[key])
        return dashboard_data
```

### 2. OWL QWeb Template Extension (`static/src/xml/time_off_card.xml`)

Extend `hr_holidays.TimeOffCard`, `hr_holidays.TimeOffCardMobile`, and `hr_holidays.TimeOffCardPopover`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates id="template" xml:space="preserve">
    <t t-name="my_module.TimeOffCard" t-inherit="hr_holidays.TimeOffCard" t-inherit-mode="extension">
        <xpath expr="//t[@name='duration_unit']" position="replace">
            <t t-if="data.request_unit == 'minute'">minutes</t>
            <t t-elif="data.request_unit == 'hour' || props.data['overtime_deductible']" name="duration_unit">hours</t>
        </xpath>
        <xpath expr="//span[hasclass('o_timeoff_validity')]//t[@t-if=&quot;data.request_unit == 'hour'&quot;]" position="replace">
            <t t-if="data.request_unit == 'minute'">minutes</t>
            <t t-elif="data.request_unit == 'hour'">hours</t>
        </xpath>
    </t>

    <t t-name="my_module.TimeOffCardMobile" t-inherit="hr_holidays.TimeOffCardMobile" t-inherit-mode="extension">
        <xpath expr="//t[@name='duration_type']//t[@t-if=&quot;data.request_unit == 'hour'&quot;]" position="replace">
            <t t-if="data.request_unit == 'minute'">minutes</t>
            <t t-elif="data.request_unit == 'hour'">Hours</t>
        </xpath>
        <xpath expr="//span[hasclass('o_timeoff_card_mobile')]//t[@t-else=&quot;&quot;]//t[@t-if=&quot;data.request_unit == 'hour'&quot;]" position="replace">
            <t t-if="data.request_unit == 'minute'">minutes</t>
            <t t-elif="data.request_unit == 'hour'">Hours</t>
        </xpath>
        <xpath expr="//span[hasclass('o_timeoff_card_mobile')]//t[@t-if=&quot;props.data['request_unit'] == 'hour'&quot;]" position="replace">
            <t t-if="props.data['request_unit'] == 'minute'">minutes</t>
            <t t-elif="props.data['request_unit'] == 'hour'">Hours</t>
        </xpath>
    </t>

    <t t-name="my_module.TimeOffCardPopover" t-inherit="hr_holidays.TimeOffCardPopover" t-inherit-mode="extension">
        <xpath expr="//t[@t-if=&quot;props.request_unit == 'hour'&quot;]" position="replace">
            <t t-if="props.request_unit == 'minute'"> minutes</t>
            <t t-elif="props.request_unit == 'hour'"> hours</t>
        </xpath>
    </t>
</templates>
```

### 3. Register Assets & Restart Server

In `__manifest__.py`:
```python
    'assets': {
        'web.assets_backend': [
            'my_module/static/src/**/*',
        ],
    },
```

## ⚠️ Pitfalls

- **Do NOT alter `hr.leave.type.request_unit` in DB:** Changing the leave type model breaks timesheets, attendance deduction, and payroll work entries.
- **Manifest assets change:** As detailed in `setup/manifest-assets-change-needs-server-restart.md`, adding new static assets requires restarting the Odoo server process.
- **Float precision:** Always round minutes (`round(val * 60, 2)`) and check `rounded.is_integer()` before casting to integer to avoid rendering `79.99999999999999`.

## Verification

Run test suite asserting conversion on dashboard while verifying DB records remain untouched:
```bash
odoo-bin -c solargy.conf -u solargy_hr --test-enable --test-tags /solargy_hr:TestTimeOffDashboardMinutes --stop-after-init
```

## References

- Related file: `setup/manifest-assets-change-needs-server-restart.md`
- Target view: `hr_holidays.hr_leave_employee_view_dashboard`
