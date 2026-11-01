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

### KPI Computed Metrics Isolation
When feeding new computed metrics into a KPI engine from an extension module, wrap the calculation in a `try...except` and return a safe default (like `0.0`). This prevents the entire KPI evaluation loop from failing if one metric's dependencies are broken.

```python
    def _kpi_compute_source(self, source_code):
        self.ensure_one()
        if source_code == 'tm_compliance_pct':
            try:
                return max(0.0, min(100.0, self._kpi_src_tm_compliance()))
            except Exception as e:
                _logger.warning("tm_compliance_pct failed on eval %s: %s", self.id, e)
                return 0.0
        return super()._kpi_compute_source(source_code)
```

## ⚠️ Pitfalls
- Do NOT catch specific exceptions if you want total isolation; catching `Exception` guarantees safety for the core process.
- Avoid heavy logic inside the `try` block that could cause memory/timeout issues, as timeouts might not be cleanly caught depending on the environment.

## Odoo Versions
V16, V17, V18, V19+

## Last Verified
2026-06-23
