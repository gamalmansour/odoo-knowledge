# Silent UI Dropdown Absence in OWL Client Actions due to Python/JS Dictionary Key Casing Mismatch

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `owl`, `client-action`, `javascript`, `casing`, `silent-failure`, `ui-gap`, `json-rpc`

---

## Problem

In a custom OWL Client Action (e.g. interactive 3D visualizer, dashboard, or matrix report), a header `<select>` dropdown intended to allow users to switch between projects/entities never appears on the screen.

The user is permanently locked into whatever default record was loaded first, seeing only static title text with no ability to switch contexts. No JavaScript errors or warnings appear in the browser console, and the network RPC request returns HTTP 200 with status "success".

```xml
<!-- In QWeb Template -->
<t t-if="state.allProjects.length > 1">
    <select t-on-change="onProjectChange">
        <t t-foreach="state.allProjects" t-as="prj" t-key="prj.id">
            <option t-att-value="prj.id"><t t-esc="prj.name"/></option>
        </t>
    </select>
</t>
<t t-else="">
    <h5><span t-esc="state.project.name"/></h5>
</t>
```

## Root Cause

The Python backend method (`@api.model`) returned dictionary keys formatted in Python standard `snake_case`:
```python
return {
    'project': {'id': target.id, 'name': target.name},
    'all_projects': all_projects,   # <--- snake_case
    ...
}
```

While the frontend OWL JavaScript component setup assigned component state using JavaScript `camelCase`:
```javascript
this.state.allProjects = data.allProjects || [];  // <--- data.allProjects is undefined!
```

Because `data.allProjects` evaluated to `undefined`, `this.state.allProjects` defaulted to `[]` (empty array of length 0). Consequently, `<t t-if="state.allProjects.length > 1">` was always `false`, triggering `<t t-else="">` and rendering plain static text without the dropdown.

## Solution ✅

### 1. Dual Casing in Backend RPC Method (Defensive Programming)

In the Python model method, provide both snake_case and camelCase keys to remain resilient to frontend naming conventions:

```python
return {
    'project': {
        'id': target_project.id,
        'name': target_project.name,
    },
    'all_projects': all_projects,
    'allProjects': all_projects,   # Both conventions supported
    'units': units_data,
}
```

### 2. Dual Fallback in Frontend OWL Component

In the JavaScript component's data loading method, defensively read both casings:

```javascript
this.state.allProjects = data.allProjects || data.all_projects || [];
```

### 3. Comprehensive Project Discovery

Ensure the backend search captures all eligible records (e.g., projects that have child records or match profile criteria) rather than relying on a narrow domain:

```python
projects_with_units = self.search([('project_id', '!=', False)]).mapped('project_id')
dev_projects = project_obj.search([
    '|',
    ('id', 'in', projects_with_units.ids),
    '|',
    ('project_nature', '=', 'development'),
    ('profile_id.project_nature', '=', 'development'),
], order='name asc')
```

### 4. Robust State Reset on Context Switch

When the user changes the selected option in the dropdown, reset view filters, active levels, camera targets, and close open detail drawers:

```javascript
async onProjectChange(ev) {
    const newProjId = parseInt(ev.target.value, 10);
    if (newProjId && newProjId !== this.state.project?.id) {
        this.state.activeFloor = "all";
        this.state.activeStateFilter = "all";
        this.state.isExploded = false;
        this.closeDrawer();
        await this.loadProjectData(newProjId);
        this.rebuildScene();
        this.resetCamera();
    }
}
```

## ⚠️ Pitfalls

- **Silent Degrade in `<t t-if>`**: QWeb `<t t-if>` evaluates `undefined.length` or `[].length > 1` as `false` without warning, making key mismatch errors completely invisible during regular automated testing unless explicitly checked in unit assertions.
- **Server Restart Required**: In dev mode, Python code changes in backend methods (`@api.model`) are cached in memory by the running server process; a restart of the Odoo server is required for the new dictionary keys to take effect.

## Verification

1. Inspect the RPC response in the browser network tab or via python test:
   `assertIn('allProjects', data)` and `assertIn('all_projects', data)`
2. Verify that the `<select>` element renders on screen with all eligible options and that switching options updates the 3D scene smoothly.
