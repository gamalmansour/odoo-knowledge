# XML Syntax Error due to JavaScript && in QWeb

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-06-28                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `qweb`, `xml`, `javascript`, `syntax error`

---

## Problem

> When adding inline JavaScript inside a `<script>` tag within a QWeb XML view, Odoo throws an `xmlParseEntityRef: no name` error if you use `&&` (logical AND).

```
lxml.etree.XMLSyntaxError: xmlParseEntityRef: no name, line 2530, column 46
```

## Root Cause

> The XML parser (lxml) interprets the `&` character as the start of an XML entity (like `&amp;`). Since `&&` is not a valid XML entity, the parser crashes before the QWeb template is even loaded into the database.

## Solution ✅

> **Option 1 (Recommended): Refactor Logic**
> Rewrite the JavaScript logic to avoid using `&&` and `<`. For example, instead of `if (a && b)`, use nested `if` statements:
> ```javascript
> if (a) {
>     if (b) {
>         // do something
>     }
> }
> ```
>
> **Option 2: CDATA**
> Wrap the JavaScript content inside a CDATA section so the XML parser ignores it:
> ```xml
> <script type="text/javascript">
> //<![CDATA[
>     if (a && b) { ... }
> //]]>
> </script>
> ```
>
> **Option 3: Escaping**
> Escape the ampersand as `&amp;&amp;` (Not recommended, can be confusing to read).

## ⚠️ Pitfalls

- Using `<` or `>` in JavaScript loops (e.g., `for (let i = 0; i < 10; i++)`) will also cause similar XML parsing errors (`<` looks like a new tag). Use CDATA or alternative logic.
