# Construction Financial & Cost Control Enhancements

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | 17                                         |
| Severity      | 🟢 Low                                     |
| Last Verified | 2026-07-08                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `finance`, `taxes`, `depreciation`, `wip`, `poc`, `cashflow`

---

## Problem

> Standard Odoo does not fully support complex construction accounting requirements out of the box, specifically:
> 1. Variable Taxes (VAT, Withholding) on retention and advances.
> 2. Distribution of Equipment Depreciation to project cost centers based on actual working hours.
> 3. Work-In-Progress (WIP) and Revenue Recognition based on Percentage of Completion (POC) derived from *actual costs* rather than just billed amounts.
> 4. Consolidated Cash Flow Forecasting across multiple projects to determine peak financing needs.

## Root Cause

> Standard Odoo modules (Accounting, Projects, Assets) operate mostly independently and are designed for general trading/manufacturing. Construction requires tight coupling of these modules around the `construction.project` and `construction.contract` entities.

## Solution ✅

> The following architectural enhancements have been implemented:

### 1. Taxes on Contracts & Invoices
- **Implementation**: Added tax computation logic to handle variable tax rates. 
- **Method**: The contract (`construction.contract`) and invoices now factor in dynamic tax fields that adjust net and gross values appropriately for retentions and advance recoveries.

### 2. Equipment Depreciation Distribution
- **Implementation**: Extended `construction.equipment` to link with `account.asset` (`asset_id`).
- **Method**: When depreciation entries (`account.move`) are posted, a custom logic (`_post` override) checks for linked equipment and distributes the depreciation cost to project analytic accounts based on the equipment's actual operating hours logged in timesheets/daily logs.

### 3. WIP & Revenue Recognition (Actual Cost POC)
- **Implementation**: Added `cogs_recognized` and `revenue_recognized` to `construction.project`.
- **Method**: 
  - Percentage of Completion (POC) is now calculated as `(cogs_recognized + current_actual_costs) / total_budget`.
  - A wizard (`construction.project.wip.recognition.wizard`) calculates the required journal entries to move costs from the WIP account to COGS, and recognizes Revenue proportionately.

### 4. Consolidated Cash Flow
- **Implementation**: Created `construction.consolidated.cashflow` model.
- **Method**: Aggregates the time-phased cash flows (`construction.cashflow.line`) from all active projects within the company. Calculates `peak_financing_need` and `projected_final_cash` to provide treasury visibility across the portfolio.

## ⚠️ Pitfalls

- **Depreciation Distribution**: Ensure that equipment working hours are accurately logged *before* the depreciation board posts the entries, otherwise, the cost will remain in the unallocated pool.
- **WIP Recognition**: Requires strict discipline in booking actual costs (vendor bills, timesheets, inventory moves) prior to running the end-of-month WIP recognition wizard.
- **Cash Flow**: The accuracy of the consolidated cash flow heavily depends on the individual project budgets, start/end dates, and collection lag configurations.

## References

- Related modules: `construction_project`, `construction_contract`, `construction_cashflow`
