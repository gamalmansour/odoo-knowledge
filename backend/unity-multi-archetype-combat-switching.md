# Unity Multi-Archetype Combat & Weapon Switching Architecture

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `combat`, `character-switching`, `genshin`, `weapons`, `mobile`

---

## Problem

In Genshin-style Action RPG games with party switching (Melee Sword, Ranged Bow, Mystic Catalyst):
1. Swapping character skins while preserving player locomotion causes combat state desync: attack hitboxes, animations, and projectile spawns continue using the old archetype parameters or misfire.
2. Direct melee hitboxes often fail to apply damage to parent entity hitboxes (`EnemyBase`) unless recursively traversed up the hierarchy (`GetComponentInParent<EnemyBase>()`).
3. Switching weapons without synchronizing active elemental types breaks the Elemental Reaction loop (Swirl, Vaporize, Melt).

```
// Bug symptom: Switching to archer still performs sword swing or ranged projectiles deal 0 damage
```

## Root Cause

- Weapon objects and combat controllers are typically treated as isolated systems. If `PlayerCombatSystem` is not directly notified when `CharacterWardrobeManager` swaps active hero meshes, the weapon visual model changes but the combat logic remains stuck in the prior style.
- Compound colliders on complex monsters or bosses (like Shielded Elites) have child colliders with no scripts attached. `hit.GetComponent<EnemyBase>()` returns `null` unless defensive fallback `hit.GetComponentInParent<EnemyBase>()` is used.

## Solution ✅

### 1. Synchronized Style Handoff
Expose a single atomic method on `PlayerCombatSystem`:
```csharp
public void SetCombatStyle(CombatStyle style, ElementType element)
{
    currentStyle = style;
    currentElement = element;
    currentComboIndex = 0;
    isAttacking = false;
}
```

Call this in `CharacterWardrobeManager.SwitchSkin()` whenever a character or weapon swap occurs.

### 2. Defensive Parent Collider Traversal
Always check both component and parent component:
```csharp
var enemyBase = enemy.GetComponent<EnemyBase>() ?? enemy.GetComponentInParent<EnemyBase>();
if (enemyBase != null && !enemyBase.IsDead)
{
    enemyBase.TakeDamage(damage, isCrit, currentElement, hitPoint);
}
```

### 3. Procedural Projectile Factory
For ranged bow arrows and homing catalyst glyphs, instantiate a lightweight `PlayerProjectile` with directional velocity, soft target homing, and automatic elemental aura transmission:
```csharp
PlayerProjectile.Spawn(spawnPos, aimDir, damage, isCrit, element, pType, target);
```

## ⚠️ Pitfalls

- Never destroy the player GameObject during a character switch; toggle child skin roots (`skinMeshRoot.SetActive`) to avoid resetting Physics/CharacterController momentum.
- Always provide desktop hotkeys (`1`, `2`, `3`) AND clickable UI buttons for seamless mobile touch parity.

## Verification

Run full E2E verification:
```bash
python3 test_e2e_meenysed.py
```
Output:
```
🎉 ALL 4 E2E TEST SUITES PASSED WITH 100% SUCCESS!
```
