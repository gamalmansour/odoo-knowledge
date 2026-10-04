# Equipment Fleet Management: Rental Contracts, On-Hire Filter Traps, Fuel Logs, and Maintenance Architecture

**Category:** Setup / Construction Equipment  
**Severity:** 🔴 Critical  
**Odoo Versions:** 16, 17, 18, 19  
**Tags:** `setup`, `equipment`, `fleet`, `rental-contracts`, `hired-equipment`, `on-hire-filter`, `fuel-log`, `diesel-theft`, `maintenance`, `search-view`  
**Last Verified:** 2026-10-04  

---

## Problem Description ❌

In construction equipment and fleet management suites, users navigating to:
- **Rental Contracts** (`construction.equipment.rental`)
- **Hired Equipment** (`construction.equipment.rental.line`)
- **Fuel & Diesel Logs** (`construction.equipment.fuel.log`)
- **Maintenance** (`construction.equipment.maintenance`)

frequently report that these screens are completely blank or behave unexpectedly:
1. **Empty Screens on Clean DBs:** Fleet and equipment demo data is often omitted or un-executed during initial setup, leaving all rental contracts, fuel dispensations, and maintenance orders empty.
2. **The "Hired Equipment" Hidden Records Trap:** The `action_equipment_rental_line` action defines a hard default search filter: `{'search_default_filter_on_hire': 1}`. If contract lines exist but haven't been transitioned via `action_on_hire()`, the screen displays **zero records** despite active contracts.
3. **Missing Form and Search Views on Top-Level Maintenance:** `action_equipment_maintenance` shipped without a dedicated search view or top-level form view, making filtering by status (Scheduled vs. Done) or grouping by machinery impossible.
4. **Fuel Log Leakage & Meter Monotonicity:** Lack of automated meter verification allows data entry personnel to enter arbitrary meter hours, hiding fuel shrinkage or negative machine hours.

---

## Symptoms / Error Messages

- **Empty Hired Equipment View:** "No records found" in `action_equipment_rental_line` even though lines were entered on rental contracts.
- **Inability to Filter Maintenance Records:** Clicking the search bar on `action_equipment_maintenance` lacks filters for Scheduled services, Breakdown repairs, or Equipment grouping.
- **Uncontrolled Fleet Spend:** Fuel vouchers logged without baseline comparison fail to flag machines consuming excessive diesel (>15% variance).

---

## Root Cause Analysis 🔍

1. **Context Filter Prerequisite:** `construction.equipment.rental.line` computes `is_on_hire = bool(date_on_hire and not date_off_hire)`. The action context `'search_default_filter_on_hire': 1` strictly matches `is_on_hire = True`. Without calling `action_on_hire()`, `date_on_hire` is null, rendering records invisible by default.
2. **Partial UI Architecture:** `construction.equipment.maintenance` had an editable-bottom list view inside equipment form tabs, but when promoted to a root menu item (`menu_equipment_maint`), it lacked its own standalone search and form view declarations.
3. **Decoupled Rental Plant vs. Owned Plant:** Hired machinery must be registered as assets (`ownership = 'hired'`) and tied to suppliers so that vendor bills from rental contracts map directly to project analytic cost centers.

---

## Solution ✅

### 1. Dedicated Search & Form Views for Maintenance

In `equipment_views.xml`, define explicit form and search views with essential filters and groupings:

```xml
<record id="view_equipment_maintenance_search" model="ir.ui.view">
    <field name="name">construction.equipment.maintenance.search</field>
    <field name="model">construction.equipment.maintenance</field>
    <field name="arch" type="xml">
        <search string="Search Maintenance">
            <field name="equipment_id"/>
            <field name="description"/>
            <field name="supplier_id"/>
            <separator/>
            <filter string="Scheduled" name="f_scheduled" domain="[('state', '=', 'scheduled')]"/>
            <filter string="Done" name="f_done" domain="[('state', '=', 'done')]"/>
            <separator/>
            <filter string="Preventive Service" name="f_preventive" domain="[('maint_type', '=', 'preventive')]"/>
            <filter string="Breakdown Repair" name="f_breakdown" domain="[('maint_type', '=', 'breakdown')]"/>
            <filter string="Inspection / Certification" name="f_inspection" domain="[('maint_type', '=', 'inspection')]"/>
            <group expand="0" string="Group By">
                <filter string="Equipment" name="grp_equipment" context="{'group_by': 'equipment_id'}"/>
                <filter string="Type" name="grp_type" context="{'group_by': 'maint_type'}"/>
                <filter string="Status" name="grp_state" context="{'group_by': 'state'}"/>
                <filter string="Workshop / Supplier" name="grp_supplier" context="{'group_by': 'supplier_id'}"/>
                <filter string="Date" name="grp_date" context="{'group_by': 'date:month'}"/>
            </group>
        </search>
    </field>
</record>

<record id="action_equipment_maintenance" model="ir.actions.act_window">
    <field name="name">Maintenance</field>
    <field name="res_model">construction.equipment.maintenance</field>
    <field name="view_mode">list,form</field>
    <field name="search_view_id" ref="view_equipment_maintenance_search"/>
</record>
```

### 2. Standalone Form View for Hired Equipment Lines

Provide a dedicated form view for `construction.equipment.rental.line` with on-hire and off-hire action triggers:

```xml
<record id="action_equipment_rental_line" model="ir.actions.act_window">
    <field name="name">Hired Equipment</field>
    <field name="res_model">construction.equipment.rental.line</field>
    <field name="view_mode">list,form</field>
    <field name="search_view_id" ref="view_equipment_rental_line_search"/>
    <field name="context">{'search_default_filter_on_hire': 1}</field>
</record>
```

### 3. Monotonic Meter Guard & Theft Anomaly Detection in Fuel Logs

Ensure `construction.equipment.fuel.log` guards against odometer rollback and enforces variance thresholds:

```python
@api.constrains('meter_reading', 'previous_meter_reading')
def _check_meter_reading_monotonic(self) -> None:
    for rec in self:
        if rec.meter_reading < rec.previous_meter_reading:
            raise ValidationError(_(
                "Non-monotonic meter reading: Current reading (%(curr).2f) cannot be less than previous reading (%(prev).2f).",
                curr=rec.meter_reading,
                prev=rec.previous_meter_reading,
            ))

@api.depends('meter_reading', 'previous_meter_reading', 'liters', 'standard_consumption_rate', 'meter_unit')
def _compute_meter_and_consumption(self):
    for rec in self:
        delta = (rec.meter_reading or 0.0) - (rec.previous_meter_reading or 0.0)
        rec.delta_meter = delta if delta > 0.0 else 0.0
        rate = (rec.liters / rec.delta_meter) if (rec.delta_meter > 0 and rec.liters > 0) else 0.0
        rec.consumption_rate = rate
        std_rate = rec.standard_consumption_rate or 0.0
        if std_rate > 0 and rate > 0:
            var_rate = rate - std_rate
            rec.variance_rate = var_rate
            var_pct = (var_rate / std_rate) * 100.0
            rec.variance_pct = var_pct
            rec.is_consumption_abnormal = var_pct > 15.0
        else:
            rec.variance_rate = 0.0
            rec.variance_pct = 0.0
            rec.is_consumption_abnormal = False
```

---

## ⚠️ Pitfalls

1. **Beware the On-Hire Default Filter:** Seeding scripts or demo generators must explicitly trigger `action_on_hire()` on confirmed rental lines, otherwise users opening "Hired Equipment" will see an empty screen due to the default filter.
2. **Double-Hire Prevention:** The system enforces `@api.constrains('equipment_id', 'date_on_hire', 'date_off_hire')` to prevent placing a unit on two open contracts concurrently.
3. **Analytic Distribution on Vendor Bills:** Rental contracts automatically pass the project's analytic account into vendor bill lines upon `action_create_bill()`, ensuring costs roll up to project CBS rather than general overhead.

---

## Verification Checklist

- [x] "Rental Contracts" lists confirmed and closed rental agreements with calculated contract values.
- [x] "Hired Equipment" displays active plant units currently on site with on-hire dates and arrival meters.
- [x] "Fuel / Diesel Logs" shows confirmed vouchers, highlights >15% abnormal consumption, and enforces justification notes.
- [x] "Maintenance" provides full list, form, and search views with Scheduled, Done, Preventive, and Breakdown filters.
