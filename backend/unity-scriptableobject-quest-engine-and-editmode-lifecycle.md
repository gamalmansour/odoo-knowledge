# Unity Data-Driven Quest Engine and EditMode Test Lifecycle Isolation

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `quest-system`, `scriptableobject`, `editmode`, `unit-testing`, `singleton`, `lifecycle`

---

## Problem

When developing data-driven modular quest engines with decoupled event channels in Unity:
1. **Hardcoding Trap:** Embedding quest titles, objective counters, and prerequisites in C# code requires client rebuilds and app store submissions for every narrative tweak.
2. **EditMode Lifecycle Silence:** `MonoBehaviour` components instantiated dynamically via `AddComponent<T>()` in Unity `-testPlatform EditMode` do not invoke `Awake()`, `OnEnable()`, or `Start()`, leaving event subscriptions and internal dictionaries uninitialized.
3. **Singleton Test Pollution:** Standard static `Instance` singletons persist across test methods within the same batch test runner domain. When test teardown destroys the `GameObject`, the cached `Instance` field references a destroyed C++ Unity object (`null` check in C# returns true, but object is not garbage collected), causing subsequent tests to either self-destruct or fail silently.
4. **`DontDestroyOnLoad` in EditMode:** Calling `DontDestroyOnLoad(gameObject)` throws an error when running outside PlayMode.

## Root Cause

1. Direct coupling of narrative definitions to script logic instead of pure data containers (`ScriptableObject`).
2. Unity EditMode test execution bypasses the normal player loop lifecycle events unless components are flagged or manually initialized.
3. C# static variables live across the entire test assembly execution process and are not automatically cleared when game objects are destroyed between test cases.

## Solution ✅

### 1. Pure ScriptableObject Architecture (`QuestData.cs`)
Separate runtime execution from authoring. All objectives, rewards, and strings are authored in `.asset` files:

```csharp
[CreateAssetMenu(fileName = "Quest_", menuName = "MeenYsed/Quests/Quest Data", order = 10)]
public class QuestData : ScriptableObject
{
    public string questId;
    public string questTitleArabic;
    public List<QuestObjectiveData> objectives = new List<QuestObjectiveData>();
    public QuestReward rewardBundle;
}
```

### 2. `[ExecuteAlways]` and Explicit `Initialize()` Method
Decorate the manager with `[ExecuteAlways]` and provide a dedicated initialization entrypoint that runs in both EditMode unit tests and live PlayMode:

```csharp
[ExecuteAlways]
public class QuestManager : MonoBehaviour
{
    public void Initialize(string customSaveDir = null)
    {
        saveDirectory = customSaveDir ?? Application.persistentDataPath;
        LoadQuestDatabase();
        LoadProgress();
        SubscribeToEvents();
    }
}
```

### 3. Clean Singleton Teardown on `OnDestroy`
Ensure the static singleton reference is cleared immediately upon destruction:

```csharp
private void OnDestroy()
{
    if (Instance == this)
    {
        Instance = null;
    }
    UnsubscribeFromEvents();
    QuestEvents.ResetAllListeners();
}
```

### 4. Guarded `DontDestroyOnLoad`
```csharp
if (Application.isPlaying)
{
    DontDestroyOnLoad(gameObject);
}
```

## ⚠️ Pitfalls

- **Static Event Leaks:** Static event buses (e.g. `QuestEvents.OnNPCInteracted`) retain delegates across test cases unless explicitly cleared with a `ResetAllListeners()` helper in test fixtures (`[TearDown]`).
- **Path Isolation in Unit Tests:** Always provide a temporary sandbox directory for disk serialization in tests (`Path.Combine(Application.temporaryCachePath, Guid.NewGuid().ToString())`) to avoid overwriting player save files.

## Verification

Run automated quest engine unit tests via Unity batchmode:
```bash
/Applications/Unity/Hub/Editor/6000.6.0f1/Unity.app/Contents/MacOS/Unity \
  -batchmode -nographics -projectPath "Phoenix_Vertical_Slice" \
  -runTests -testPlatform EditMode -testFilter QuestEngineTests
```
