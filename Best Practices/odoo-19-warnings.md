# Odoo 19 Common Installation Warnings

## 1. `_sql_constraints` Deprecation
**Warning:** `Model attribute '_sql_constraints' is no longer supported, please define model.Constraint on the model.`

### ⚠️ Pitfall
In Odoo 19, the legacy `_sql_constraints = [...]` list attribute has been completely deprecated and will throw a warning on module load.

### Solution ✅
Define the constraint directly on the class as an attribute using `models.Constraint`:

**Old (Odoo 18-):**
```python
_sql_constraints = [
    ('name_company_uniq', 'unique (name, company_id)', 'The company name must be unique per company!')
]
```

**New (Odoo 19+):**
```python
_name_company_uniq = models.Constraint(
    'unique (name, company_id)', 
    'The company name must be unique per company!'
)
```

## 2. Translation `_()` inside Constraints
**Warning:** `no translation language detected, skipping translation`

### ⚠️ Pitfall
Never wrap constraint string messages with `_()` inside the Model class definition. Constraints are evaluated when the module is imported, before the environment or language context exists.

### Solution ✅
Remove `_()` from constraint string definitions. Odoo extracts these automatically for `.pot` files without needing the wrapper.

## 3. `tracking=True` on Non-Tracking Models
**Warning:** `Field [...]: unknown parameter 'tracking', if this is an actual parameter you may want to override the method _valid_field_parameter...`

### ⚠️ Pitfall
You added `tracking=True` to a field, but the model does not inherit from `mail.thread`. In Odoo 19, this produces an explicit warning instead of silently ignoring it.

### Solution ✅
Either inherit `['mail.thread']` in the model, or remove `tracking=True` from the field definition.

## 4. Duplicate Field Labels
**Warning:** `Two fields ([...]) of [...] have the same label...`

### ⚠️ Pitfall
Multiple fields on the same model share the exact same `string='...'` attribute, which causes confusion in the UI (e.g., Studio, Import/Export).

### Solution ✅
Ensure `string` attributes are unique per model. For example, change `string='Driver'` to `string='Driver Name'` for character fields.

## 5. Accessibility (a11y) Warning for Icons
**Warning:** `A <i> with fa class (...) must have title in its tag, parents, descendants or have text`

### ⚠️ Pitfall
In Odoo 19+, the framework enforces accessibility standards for views. If you use a FontAwesome icon (`<i>`) without any inner text or descriptive attributes, Odoo throws a warning because screen readers cannot interpret the icon.

### Solution ✅
Always add a `title` or `aria-label` attribute to empty `<i>` tags in XML views.

**Old (Odoo 18-):**
```xml
<i class="fa fa-calendar me-1"/>
```

**New (Odoo 19+):**
```xml
<i class="fa fa-calendar me-1" title="Date" aria-label="Date"/>
```

## 6. Invalid view type: 'tree'
**Warning:** `odoo.tools.convert.ParseError: while parsing ... ParseError: Invalid view type: 'tree'`

### ⚠️ Pitfall
In Odoo 19, the `<tree>` tag for list views has been completely removed. Using `<tree>` will cause a hard parse error preventing the module from loading.

### Solution ✅
Change all `<tree>` tags in your XML views to `<list>`. Also update `view_mode="tree,form"` to `view_mode="list,form"` in your window actions.

**Old (Odoo 18-):**
```xml
<tree>
    <field name="name"/>
</tree>
```

**New (Odoo 19+):**
```xml
<list>
    <field name="name"/>
</list>
```

## 7. Search view `<group>` accepts no attributes

**Error:** `ParseError: Invalid view <model>.search definition`, preceded by
`RELAXNG_ERR_INVALIDATTR: Invalid attribute expand for element group` and a
misleading `Element search has extra content: field`.

### ⚠️ Pitfall
The pre-19 idiom for a Group By block —

```xml
<group expand="0" string="Group By">
    <filter name="groupby_x" string="X" context="{'group_by': 'x'}"/>
</group>
```

— is rejected outright. `odoo/addons/base/rng/common.rng` defines `group` with
`colspan/rowspan/fill/height/width/name/color/invisible` and nothing else, so
`expand` fails validation. The follow-on "search has extra content" line is
RELAX NG cascade noise, not a second problem: chasing it wastes the debugging.

This is a **hard install failure**, not a warning — the module will not load,
and no amount of static XML checking catches it because the file is perfectly
well-formed XML.

### Solution ✅
Bare `<group>`, which is what Odoo 19 core now ships everywhere:

```xml
<group>
    <filter name="groupby_x" string="X" context="{'group_by': 'x'}"/>
</group>
```

Audit an existing module with:

```bash
grep -rn 'expand=' --include='*.xml' .   # must return nothing
```

> Also recorded inside `orm/o2c-project-phase-workflow-pattern.md`, where it is
> effectively unfindable — nobody debugging a search view searches for an O2C
> workflow entry. Kept here as the discoverable copy.

## 8. Demo data is OPT-IN in Odoo 19 — `--without-demo` is now the default

**Symptom:** a fresh `-d newdb -i my_module` install succeeds, the module's
`data` files load, and **nothing from `demo/` appears**. No error, no warning.

### ⚠️ Pitfall
The flag polarity flipped. In `odoo/tools/config.py`:

```python
group.add_option("--with-demo", dest="with_demo", action='store_true', my_default=False,
                 help="install demo data in new databases")
group.add_option("--without-demo", dest="with_demo", type='without_demo', ...,
                 help="don't install demo data in new databases (default)")
```

`my_default=False` — so every muscle-memory command carried over from Odoo ≤18
(where demo loaded unless you said `--without-demo=all`) now silently produces a
demo-free database. `load_modules` passes `install_demo=new_db_demo`, which is
that same flag, and demo only ever loads while the database is **new**.

### Solution ✅
```bash
./odoo-bin -c conf -d newdb -i my_module --with-demo --stop-after-init
```

Verify rather than trust the absence of an error:

```sql
SELECT name, state, demo FROM ir_module_module WHERE name = 'my_module';
-- demo = t means the demo data actually ran
```

### ⚠️ Pitfalls
- Adding `--with-demo` to an **existing** database does nothing: the module is
  already `installed`, and demo is a new-database decision. Drop and recreate.
- `load_demo()` swallows failures with a `WARNING ... demo data failed to
  install, installed without demo data` and carries on, so a broken demo file
  looks identical to demo being switched off. Check the `demo` column to tell
  the two apart.
- Demo data that must be dated relative to install time (anything a "last seven
  days" report reads) cannot live in static XML — call a model method from the
  demo file with `<function model="my.model" name="_populate_demo"/>`.

## 9. Group changes made from a second process need a server restart

Granting a group via `odoo-bin shell` (or straight SQL) while a server is
running leaves that server serving `AccessError` from its `ormcache`: user group
membership is cached in the registry, and a `cr.commit()` in another process
raises no registry signal. The database is right and the app still says no.

Restart the server process — or make the change through the running server's own
UI/RPC, which invalidates the cache properly.

