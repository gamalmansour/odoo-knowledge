# Unity Mobile: Arabic RTL Text Rendering, Contextual Glyph Shaping, and BiDi Run Grouping

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `mobile`, `arabic`, `rtl`, `bidi`, `shaping`, `ui`, `ios`

---

## Problem

When displaying Arabic text inside Unity mobile games using `UnityEngine.UI.Text`, IMGUI (`GUI.Label`, `GUI.Button`), or legacy TextMeshPro components, Arabic characters render visibly broken:
- Characters appear disconnected and in their isolated glyph forms (e.g. `م ي ن  ي س د` instead of `مين يسد`).
- Text is laid out in Left-To-Right (LTR) order rather than Right-To-Left (RTL).
- Numbers and mixed Latin text (e.g., `"Meen Ysed (أحمد)"`) are reversed or corrupted (e.g. `"(Ahmed) demhA"`).
- Punctuation and brackets are inverted or placed on the wrong side.

## Root Cause

1. **Absence of Runtime Complex Script Shaping Engine:**
   Unlike web browsers or native mobile OS text views (CoreText / HarfBuzz), Unity’s standard font rendering pipeline does not perform runtime Arabic OpenType contextual glyph substitution. Logical Unicode Arabic strings (`\u0600`–`\u06FF`) are treated as independent glyphs.
2. **Naive BiDi Inversion Pitfall:**
   Simply reversing string characters or splitting by whitespace and reversing words breaks multi-word Latin phrases (e.g., `"Meen Ysed"` becomes `"Ysed Meen"`), and flips numbers (e.g., `2500` becomes `0052`).
3. **Punctuation & Bracket Asymmetry:**
   Parentheses `()`, brackets `[]`, braces `{}`, and Arabic quotation marks `«»` have logical orientations that must be flipped when rendered in an RTL visual stream.

## Solution ✅

### 1. Architectural Arabic Shaping Engine (`ArabicSupport.cs`)
Implement a standalone, zero-dependency Arabic shaping engine that:
1. **Maps Logical Characters to Presentation Forms-B (`\uFE80`–`\uFEFC`):**
   Examines preceding and following characters to select the appropriate glyph form:
   - **Isolated** (Default / standalone)
   - **Initial** (Connected to following letter)
   - **Medial** (Connected on both sides)
   - **Final** (Connected to preceding letter)
2. **Handles Lam-Alef Ligatures:**
   Detects combinations of Lam (`ل`) followed by Alef (`ا`, `أ`, `إ`, `آ`) and converts them to compound ligatures (`\uFEF5`–`\uFEFC`).
3. **Preserves Diacritics (Tashkeel):**
   Maintains Fatha, Damma, Kasra, Sukun, Tanween, and Shadda in the visual stream without breaking connectivity.
4. **BiDi Run Grouping (`GroupRuns`):**
   Segments paragraphs into atomic runs:
   - Arabic words and punctuation are shaped and reversed for visual RTL display.
   - Non-Arabic segments (consecutive English words, numbers, and inter-word spaces) are grouped into single atomic LTR blocks so internal order remains intact (`"Meen Ysed"` stays `"Meen Ysed"`, not `"Ysed Meen"`).
5. **Unicode Punctuation Mirroring:**
   Mirrors open/close brackets `( )` ↔ `) (`, `[ ]` ↔ `] [`, `{ }` ↔ `} {`, `« »` ↔ `» «`, and translates question marks `?` ↔ `؟`.

### 2. Extension Methods & Helpers (`ArabicTextHelper.cs`)
Provide clean extension methods for runtime use:
```csharp
public static class ArabicTextHelper
{
    public static string ToArabic(this string text)
    {
        return ArabicSupport.Fix(text);
    }
}
```

### 3. Mobile UI Adaptations
- **Platform Separation:** Conditionally hide desktop shortcuts (`[1]`, `[2]`, `Press Space`) on mobile touch devices (`Application.isMobilePlatform`).
- **Touch Ergonomics:** Ensure minimum touch target sizes ($\ge 48\times 48\text{ dp}$) for buttons and character selection cards.
- **Safe Area Insets:** Clamp UI containers to `Screen.safeArea` to avoid notch and home indicator cutoffs.

## ⚠️ Pitfalls

- **Overwriting Non-Arabic Runs:** Never reverse characters of an English token or number. Treat the entire consecutive English phrase as an atomic LTR token.
- **Tashkeel Index Offsets:** Ensure connectivity check methods peek past Tashkeel characters when determining preceding/following connectivity.
- **Unity Re-export Overwriting pbxproj:** Exporting iOS projects from Unity overwrites `project.pbxproj`. Ensure `appleDeveloperTeamID` is programmatically set in `PlayerSettings.iOS.appleDeveloperTeamID`.

## Verification

Run automated EditMode tests verifying:
1. Isolated letters (`"ب"` ↔ `\uFE8F`).
2. Connected words (`"مين يسد"` ↔ proper Presentation Forms).
3. Lam-Alef ligatures (`"لا"` ↔ `\uFEFB`).
4. Tashkeel diacritics.
5. Mixed Arabic and English (`"مين يسد (The Phoenix)"`).
6. Numbers (`"2500 XP"`).
7. Physical device screenshot via `xcrun devicectl device capture screenshot`.
