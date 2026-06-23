# Module Extension Isolation (Degrade to No-op)

## Scenario
You need to trigger logic in an extension module during a core process (like `action_start_visit`), but the core process MUST NOT break if the extension logic fails (e.g., due to missing fields, bad data, or removed dependencies).

## Solution ✅
Wrap the extension logic call in a generic `try...except Exception:` block and `pass`. This ensures the extension degrades to a no-op instead of raising a traceback and blocking the entire business process.

```python
    def action_start_visit(self, latitude=None, longitude=None, ip_addr=None) -> bool:
        res = super().action_start_visit(latitude=latitude, longitude=longitude, ip_addr=ip_addr)
        for visit in self:
            try:
                visit.action_load_tm_checkpoints()
            except Exception:
                pass  # Degrade to no-op
        return res
```

## ⚠️ Pitfalls
- Do NOT catch specific exceptions if you want total isolation; catching `Exception` guarantees safety for the core process.
- Avoid heavy logic inside the `try` block that could cause memory/timeout issues, as timeouts might not be cleanly caught depending on the environment.

## Odoo Versions
V16, V17, V18, V19+

## Last Verified
2026-06-23
