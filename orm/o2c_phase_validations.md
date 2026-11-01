# O2C Framework: Centralized State Machine Validation

**Severity:** 🟡 Medium

**Tags:** `#architecture`, `#o2c`, `#validation`, `#state-machine`
**Odoo Versions:** `17.0`, `18.0`, `19.0`
**Last Verified:** 2026-05-21

## The Problem
When implementing a massive framework like Order-to-Cash (O2C) across multiple Sprints, you end up with dozens of compliance checks (e.g., Award Package validated, Budget approved, Charter signed, PMP baselined, Kickoff confirmed, Delivery Notes approved). If you put validation logic inside the `write` methods of 10 different models, the system becomes an unmaintainable spiderweb. The 6-month pre-mortem identified that complex phase transitions would fail silently or cause locking issues if spread out.

## The Solution ✅
Centralize all phase transition logic into a single method on the master model (`project.project`).
Instead of checking conditions everywhere, we added `o2c_phase` to `project.project` as the master statusbar. We override `write` on `project.project` and intercept any change to `o2c_phase` to run `_validate_o2c_transition(target_phase)`.

```python
    def write(self, vals: dict) -> bool:
        if 'o2c_phase' in vals:
            target_phase = vals['o2c_phase']
            for project in self:
                project._validate_o2c_transition(target_phase)
            # Auto-record KPI dates here cleanly
            if target_phase == 'execution':
                vals.setdefault('execution_ready_date', fields.Date.today())
        return super().write(vals)

    def _validate_o2c_transition(self, target_phase: str) -> None:
        # Dictionary of validations per target phase
        if target_phase == 'planning':
            if not self.analytic_account_id:
                raise UserError(_('A Cost Center must be assigned.'))
        # ... and so on for execution, support, closing, archived
```

## ⚠️ Pitfalls
- **Don't hardcode IDs:** Always check relations (`if not self.pmp_id:`).
- **Security Context:** If the validation checks fields the user doesn't have access to, it will crash. We used `sudo()` for reading related model states if needed, but standard Odoo record rules usually suffice.
- **Transitional States:** Make sure you handle backwards transitions (e.g., moving from Execution back to Planning) explicitly if they shouldn't trigger the same strict checks as moving forward.

## See Also
- NT-Process-Order to Cash SOP documentation.
