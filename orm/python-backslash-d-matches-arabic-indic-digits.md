# `\d` in Python Matches Arabic-Indic Digits — a 14-Digit National ID Validator That Accepts ٥٦٤٦٧٥٤٦٥٥٤٣٦٧

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `validation`, `regex`, `python`, `unicode`, `arabic`, `national-id`, `vat`, `localization`, `eta`, `silent-failure`

---

## Problem

> A validator meant to enforce "exactly 14 digits" accepts a value no downstream system
> can read, and raises nothing:

```python
re.match(r'^\d{14}$', '٥٦٤٦٧٥٤٦٥٥٤٣٦٧')   # -> MATCH  🔴
```

Those are Eastern Arabic-Indic digits (U+0660–U+0669), typed on an Arabic keyboard. The
value looks like a national ID to the validator, is stored, and then:

- **ETA / e-invoicing rejects it** — the tax authority expects Western digits;
- **banks and government portals reject it**;
- **searching `56467546554367` never finds the record** — different code points;
- the number is *correct*; only the script is wrong, which is why nobody spots it by eye.

On the live data one order (`S04674`) was confirmed this way before the validator was
questioned. Only **1 partner of 1,529** was affected — the failure is rare enough to
survive testing and common enough to reach production.

## Root Cause

In Python 3, a `str` pattern is Unicode-aware by default. `\d` is **not** `[0-9]` — it is
every character with the Unicode `Nd` (decimal number) property: Arabic-Indic ٠-٩,
Persian ۰-۹, Devanagari ०-९, and dozens more.

```python
len(re.sub(r'\D', '', '٥٦٤٦٧٥٤٦٥'))   # -> 9   — it counts them as digits too
```

So both the *match* and any *digit count* built on `\d` agree that an Arabic-Indic string
is a valid run of digits.

## Solution ✅

**Write the character class you actually mean.**

```python
NATIONAL_ID_PATTERN = re.compile(r'^[0-9]{14}$')     # ✅ ASCII only
# re.compile(r'^\d{14}$')                            # ❌ accepts ٥٦٤...
# re.compile(r'^\d{14}$', re.ASCII)                  # also correct, easier to lose in a diff
```

**Then tell the user what is actually wrong.** A bare refusal makes them retype the same
characters and fail again — the number *is* right:

```python
ARABIC_INDIC_DIGITS = {
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
}

western = ''.join(ARABIC_INDIC_DIGITS.get(c, c) for c in value)
if western != value and PATTERN.match(western):
    raise UserError(_(
        "… is written in Arabic-Indic digits (%(value)s). It must be stored in "
        "Western digits so that e-invoicing, banks and search can read it.\n\n"
        "Enter it as: %(western)s", value=value, western=western))
```

Persian ۰-۹ (U+06F0–U+06F9) render almost identically to Arabic-Indic for four of the ten
glyphs — map both, or a Farsi keyboard produces the same bug with a different code point.

## ⚠️ Pitfalls

- **The same trap in `\w` and `\s`.** `\w` matches Arabic letters, Cyrillic, CJK; `\s`
  matches U+00A0 and other Unicode spaces. Whenever the intent is "ASCII", say `[0-9]`,
  `[A-Za-z0-9_]`, or pass `re.ASCII`.
- **`str.isdigit()` is worse**: `'٥'.isdigit()` is `True`, and so is `'²'`. `str.isascii()
  and str.isdigit()` is the pair that means what you want.
- **`int()` converts them silently**: `int('٥٦٤')` → `564`. Code that parses instead of
  validating will "work" and hide the problem one layer further down.
- **This is invisible in a code review and in most test data.** Nobody writes an
  Arabic-Indic test fixture unless they have been bitten. Add one.
- **Validate at the transaction, not with a constraint on the field**, when historical
  data is already dirty: an `@api.constrains` on `res.partner.vat` blocks every edit of
  every pre-existing bad record, including edits that have nothing to do with the ID.
- **Check the existing data before shipping the fix** — the count tells you whether this
  is a code fix or a data cleanup as well:

```sql
SELECT count(*) FROM res_partner WHERE vat ~ '[٠-٩۰-۹]';
```

## Verification

```python
import re
P = re.compile(r'^[0-9]{14}$')
assert not P.match('٥٦٤٦٧٥٤٦٥٥٤٣٦٧')      # Arabic-Indic, 14 chars
assert     P.match('56467546554367')       # Western, 14 digits
assert not P.match('٥٦٤٦٧٥٤٦٥')            # short and Arabic-Indic
```

```sql
-- how many records carry the wrong script today
SELECT name, vat FROM res_partner WHERE vat ~ '[٠-٩۰-۹]';
```

## Related

- `orm/geolocation-precision-digits.md` — the other "the field accepted it, so it must be fine" class
- `models/kpi-returning-zero-for-undefined-lies-to-the-user.md` — validation that answers instead of refusing
