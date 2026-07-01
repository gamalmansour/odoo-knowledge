---
title: "OWL 2 Client Actions Empty/Blank View in Odoo 19"
category: "frontend"
tags: ["owl", "client-action", "odoo-19", "props"]
last_verified: "2026-07-01"
---

# 📝 Problem
When defining a custom OWL component as a Client Action in Odoo 19, the view renders completely blank or crashes silently, even though data is being fetched and the template exists. This often happens after upgrading an Odoo 15/16 module.

# ❌ Incorrect Approach
Defining the client action component without `props`:

```javascript
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

class MyCustomAction extends Component {
    static template = "my_module.MyCustomAction";
    // Missing props definition!
    
    setup() {
        // ...
    }
}
registry.category("actions").add("my_module.my_action", MyCustomAction);
```

# ✅ Solution
In OWL 2 (Odoo 17+), components that are instantiated by the Odoo web framework (like Client Actions via the action service) are passed several props automatically (e.g., `action`, `actionId`, `globalState`). If `static props` is not defined or is too strict, OWL will reject the props, which can cause the component to fail rendering.

Always declare `static props = ["*"];` (or explicitly define the expected props) for Client Action root components:

```javascript
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

class MyCustomAction extends Component {
    static template = "my_module.MyCustomAction";
    static props = ["*"]; // Crucial fix!
    
    setup() {
        // ...
    }
    
    // Also, when passing arrow functions to child templates in OWL 2, 
    // it's safer to define them as class properties:
    onNodeClick = (node) => {
        // ...
    }
}
registry.category("actions").add("my_module.my_action", MyCustomAction);
```

And in the XML, just reference the bound method:
```xml
<MyChildComponent node="node" onNodeClick="onNodeClick"/>
```

# ⚠️ Pitfalls (6-Month Pre-mortem)
- **Silent failures:** Developers might assume the template is wrong or the data fetch failed because there's no glaring red traceback in the Odoo UI. Always check `static props` when migrating OWL components.
- **Inline arrow functions:** While `(node) => this.onNodeClick(node)` is sometimes parsed correctly, defining the method as an arrow function on the class (`onNodeClick = (node) => { ... }`) prevents context `this` loss and avoids edge cases in the OWL template parser.
