# Bypassing Record Rules for Duplicate Validation via sudo().search_read()

**Severity:** 🟡 Medium
**Tags:** `bypass`, `record`, `rules`, `duplicate`, `validation`

## 📝 Context
When computing duplicate warnings (e.g., duplicate phone or email on `res.partner`), standard `search_count()` or `search()` will fail to detect duplicates if the existing records are hidden from the current user via Record Rules (e.g., private partners). 

## 🔴 The Problem
If a user creates a partner with phone `01000000001`, but that phone already belongs to a "Private" partner they don't have access to see, standard validation will miss it. The user will end up creating a duplicate.
Additionally, using `sudo().search_count()` inside an `@api.depends` loop causes a massive N+1 query performance bottleneck when mass-updating or importing records.

## ✅ The Solution
1. Use `sudo()` to bypass record rules and ensure all duplicates are found.
2. Use `with_context(active_test=False)` to also check against archived records.
3. Optimize with a vectorized bulk `search_read()` before the loop to prevent N+1 queries.

### Implementation Pattern

```python
    is_duplicate_phone = fields.Boolean(compute='_compute_duplicate_info', store=False)

    @api.depends('phone')
    def _compute_duplicate_info(self):
        # 1. Collect all non-empty values
        phones = [p.phone for p in self if p.phone]

        # 2. Bulk query using sudo() to bypass rules
        phone_matches = {}
        if phones:
            domain = [('phone', 'in', phones)]
            # active_test=False to ensure archived records are included in the duplicate check
            records = self.env['res.partner'].sudo().with_context(active_test=False).search_read(domain, ['phone', 'id'])
            for r in records:
                phone_matches.setdefault(r['phone'], set()).add(r['id'])

        # 3. Evaluate each record
        for partner in self:
            # Handle NewId during onchange correctly
            p_id = partner._origin.id or 0
            
            # Check if there are matching IDs OTHER than the current record's ID
            dup_phone = partner.phone and len(phone_matches.get(partner.phone, set()) - {p_id}) > 0
            
            partner.is_duplicate_phone = dup_phone
```

## ⚠️ Pitfalls
- **Do not use `search_count` in loops:** Calling `self.env['model'].sudo().search_count(...)` inside the `for partner in self:` loop will crash database performance on bulk edits.
- **Handling `NewId`:** Inside `api.depends`, unsaved records have a `NewId` type (e.g., `<NewId origin=1>`). Trying to exclude `partner.id` directly in the query domain can lead to errors. Always use `partner._origin.id` or do the exclusion locally in Python (like `- {p_id}` above).
