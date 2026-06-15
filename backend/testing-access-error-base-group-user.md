# Testing Access Errors: Missing base.group_user

**Category:** Backend  
**Tags:** Testing, Security, Groups, AccessError, Users  
**Last Verified:** 2026-06-15  
**Odoo Versions:** All  

## Context
When creating mock users for `TransactionCase` testing and assigning them custom module groups, tests might suddenly fail with `AccessError: You are not allowed to create/read '...' records`.

## Problem ⚠️
If you assign a mock user *only* to your module's custom group using a replace command `(6, 0, [group_id])`, you inadvertently strip the user of Odoo's fundamental "Internal User" privileges. 

```python
# ❌ INCORRECT: Overwrites all groups, removing base.group_user
cls.user = cls.env['res.users'].create({
    'name': 'Test User',
    'login': 'test_user',
    'groups_id': [(6, 0, [cls.env.ref('my_module.group_manager').id])]
})
```
Without `base.group_user`, the testing framework or standard Odoo methods cannot process basic base models (like `res.users`, `res.company`, basic property reads) causing cascading Access Denied errors that mask the real issue.

## Solution ✅
Always include `base.group_user` when explicitly overriding a test user's `groups_id`, or use the `(4, ID)` append command instead of `(6, 0, IDs)`.

```python
# ✅ CORRECT APPROACH 1: Include base.group_user explicitly
cls.user = cls.env['res.users'].create({
    'name': 'Test User',
    'login': 'test_user',
    'groups_id': [
        (6, 0, [
            cls.env.ref('base.group_user').id,
            cls.env.ref('my_module.group_manager').id
        ])
    ]
})

# ✅ CORRECT APPROACH 2: Append group instead of replacing
user = cls.env['res.users'].create({'name': 'User', 'login': 'u1'})
user.write({
    'groups_id': [(4, cls.env.ref('my_module.group_manager').id)]
})
```
