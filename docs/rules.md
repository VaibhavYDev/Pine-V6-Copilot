# Pine v6 Copilot — Checker Rules and Owner Verification Ledger

**Specification:** `BLUEPRINT.md` v1.1, sections 9.1–9.7  
**Document status:** Draft rule catalog and proposed test inputs; **not a record of successful Pine Editor tests**  
**Prepared:** 2026-11-11  
**Owner verification:** Pending

This file defines candidate diagnostics for Pine Script v6. It is not a copy of the official language reference, a compilation certificate, or the reusable script library. The six scripts under `tests/fixtures/` are **original small examples prepared for this project**, not copied from GitHub. They must be reviewed and manually tested by the owner before any rule is promoted to `error`.

## Mandatory evidence and severity policy

1. An `E` prefix identifies a *candidate* error family, **not** permission to emit an `error` severity. A rule is a confirmed `error` only after an exact bad snippet fails, the corrected good snippet compiles, and the owner records the real Pine Editor messages and dates here. Until then it is `warning` or disabled.
2. A `pynescript` parser failure is not proof of failure in the TradingView Pine Editor. `E00` remains a warning for unsupported or unverified syntax.
3. Record the exact fixture file, rule ID, expected line (1-based) and column (0-based), the first compiler message verbatim, whether the script compiled, the date, and optionally the content hash. Do not fill fields from a model's predictions or from a repository README.
4. A bad fixture should contain **one intentional instance of the rule under test**. Tests may assert one finding *of that rule* on its recorded line. The matching OK fixture must have **no checker errors**, while independently justified warnings may remain.
5. An exact compile result applies only to the tested content. If the file changes, re-verify it and update the recorded hash and date. Checking the syntax alone does not verify the trading strategy's logic.
6. These examples are for **offline checker fixtures**, not for trading, backtesting, profit claims, or ingestion into a production script-reuse catalog. Do not put third-party code into this file or the RAG database without documented reuse rights.
7. The owner remains responsible for severity promotions, compiler labels, the frozen evaluation set and its locks. The six fixtures in this package are not frozen benchmark tasks.
8. Do not run live TradingView automation, scraping, or an unofficial compiler API as part of this repository or its CI. Consult applicable platform terms before public deployment or publishing compiler-derived evaluation data.

**Primary language references for research** (links, not copied source):

- [Pine Script v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)
- [Script structure and version annotation](https://www.tradingview.com/pine-script-docs/language/script-structure/)
- [Global scope for plots](https://www.tradingview.com/pine-script-docs/faq/techniques/)
- [Plot limitations](https://www.tradingview.com/pine-script-docs/visuals/plots/)

## M2 owner verification — six original fixture scripts

Each example below is an **unverified draft**. The same text is included as a `.pine` file in this package. The `Pine Editor` result fields deliberately remain `NOT TESTED`. The expected line is a checker-design expectation, **not** a verified editor diagnostic location.

## E01 — Removed `when` argument on strategy orders

- **Severity:** warning
- **Evidence status:** Documentation supports the candidate rule; **Pine Editor results NOT TESTED**. Owner may change to `error` after evidence is recorded.
- **Flags:** A named `when = ...` argument passed to one of the documented applicable `strategy.*` order functions.
- **Does not flag:** `when` on an unrelated function, a user-defined function, a string/comment, or a positional argument.
- **Why:** Pine v6 removed `when` on applicable strategy order functions; use `if` to guard the order.
- **Message (template):** `when` is not supported by {function}() in Pine v6. Guard the call with `if`.
- **Reference:** https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/
- **Initial function coverage to verify:** `strategy.entry` in this pair; `strategy.order`, `strategy.exit`, `strategy.close`, `strategy.close_all`, `strategy.cancel`, `strategy.cancel_all` need separate coverage before enabling them.
- **Bad fixture:** `tests/fixtures/E01_bad.pine` — expected finding line **4**.
- **OK fixture:** `tests/fixtures/E01_ok.pine` — no finding of E01 expected; compile result pending.
- **Pine Editor, bad:** **NOT TESTED**. Compiles? `UNKNOWN`; first error (verbatim): `PENDING`; editor line: `PENDING`; date: `PENDING`.
- **Pine Editor, OK:** **NOT TESTED**. Compiles? `UNKNOWN`; warnings: `PENDING`; date: `PENDING`.
- **Expected checker warnings on OK:** None for E01; other findings must be evaluated separately.
- **Fixture SHA-256:** bad `36f2eba7b76bc729cd7838bd7f4a9b50e3fca0ed699c7e88b6f3d30b474d1173`; ok `bb9fca10dd749b7f1f25b3c6bf0f12ef8ae1ecb70244659dc48d0b9bbaaf8741` (LF-encoded exact file bytes).

**Notes:** A single tested `strategy.entry` fixture does not validate the full seven-function coverage list. Test variants individually or restrict the rule to verified functions.

**Bad — original draft:**

```pine
//@version=6
strategy("E01 Parameter Check", overlay=true)
longSignal = close > open
strategy.entry("Long", strategy.long, when=longSignal)
```


**OK — original draft:**

```pine
//@version=6
strategy("E01 Parameter Check", overlay=true)
longSignal = close > open
if longSignal
    strategy.entry("Long", strategy.long)
```

## E02 — Removed `transp` argument on plotting/visual functions

- **Severity:** warning
- **Evidence status:** Documentation supports the candidate rule; **Pine Editor results NOT TESTED**. Owner may change to `error` after evidence is recorded.
- **Flags:** A named `transp` argument on an applicable v6 visual function.
- **Does not flag:** `transp` as a local variable or in a string; custom functions with that parameter; `color.new` transparency settings.
- **Why:** Pine v6 removed the standalone `transp` parameter; transparency is supplied in the color.
- **Message (template):** `transp` is not supported by {function}() in Pine v6. Use `color.new()` when appropriate.
- **Reference:** https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/
- **Initial function coverage to verify:** `plot` in this pair; `bgcolor`, `fill`, `plotarrow`, `plotchar`, `plotshape` need separate verification.
- **Bad fixture:** `tests/fixtures/E02_bad.pine` — expected finding line **3**.
- **OK fixture:** `tests/fixtures/E02_ok.pine` — no finding of E02 expected; compile result pending.
- **Pine Editor, bad:** **NOT TESTED**. Compiles? `UNKNOWN`; first error (verbatim): `PENDING`; editor line: `PENDING`; date: `PENDING`.
- **Pine Editor, OK:** **NOT TESTED**. Compiles? `UNKNOWN`; warnings: `PENDING`; date: `PENDING`.
- **Expected checker warnings on OK:** None for E02; other findings must be evaluated separately.
- **Fixture SHA-256:** bad `b596798da21f00bd24b3f49b8896b661a1fa38b700510724e286462ac20ba0d3`; ok `a2ec6908130c9442b7d6e74d0ea84c754ee6ca47a95b9b5fcec4b293f261361b` (LF-encoded exact file bytes).

**Notes:** `color.new()` must be applied to the correct color parameter for each function. Do not blindly transplant the `plot` fix to unrelated functions.

**Bad — original draft:**

```pine
//@version=6
indicator("E02 Transparency Check", overlay=true)
plot(close, color=color.blue, transp=50)
```


**OK — original draft:**

```pine
//@version=6
indicator("E02 Transparency Check", overlay=true)
plot(close, color=color.new(color.blue, 50))
```

## E13 — Plot-like calls inside a local scope

- **Severity:** warning
- **Evidence status:** Documentation supports the candidate rule; **Pine Editor results NOT TESTED**. Owner may change to `error` after evidence is recorded.
- **Flags:** A restricted visual function call inside an `if`, `for`, `while`, `switch` or function local block.
- **Does not flag:** The same call at global scope with a conditional plotted series/color; drawings that are valid in local scope.
- **Why:** Plot-style visuals are restricted to global scope in Pine.
- **Message (template):** {function}() cannot be called in a local scope. Move it to global scope and make its series or color conditional.
- **Reference:** https://www.tradingview.com/pine-script-docs/faq/techniques/
- **Initial function coverage to verify:** `plot` inside `if` in this pair; other function/scope combinations require separate verification.
- **Bad fixture:** `tests/fixtures/E13_bad.pine` — expected finding line **4**.
- **OK fixture:** `tests/fixtures/E13_ok.pine` — no finding of E13 expected; compile result pending.
- **Pine Editor, bad:** **NOT TESTED**. Compiles? `UNKNOWN`; first error (verbatim): `PENDING`; editor line: `PENDING`; date: `PENDING`.
- **Pine Editor, OK:** **NOT TESTED**. Compiles? `UNKNOWN`; warnings: `PENDING`; date: `PENDING`.
- **Expected checker warnings on OK:** None for E13; other findings must be evaluated separately.
- **Fixture SHA-256:** bad `0d18de1b75ed09d8ad9c75e08f3fc759328e99a9ffed567a7b63cb0939b391f3`; ok `ee58a9f40a85b691979950c9b9492d9f1d0fade116358b4c59c36e716cfcc1ba` (LF-encoded exact file bytes).

**Notes:** The v1.1 blueprint lists `plot`, `plotshape`, `plotchar`, `bgcolor`, `hline`, and `fill`. Other possible global-only plotting functions belong in a future, separately verified coverage expansion.

**Bad — original draft:**

```pine
//@version=6
indicator("E13 Plot Scope Check", overlay=true)
if close > open
    plot(close, color=color.green)
```


**OK — original draft:**

```pine
//@version=6
indicator("E13 Plot Scope Check", overlay=true)
plot(close > open ? close : na, color=color.green)
```

## M2 verification record — fill manually after testing

| Rule | Bad compiles? | Bad: exact first error | OK compiles? | OK warnings | Tested date | Owner approval to promote? |
| --- | --- | --- | --- | --- | --- | --- |
| E01 | UNKNOWN | PENDING | UNKNOWN | PENDING | PENDING | NO |
| E02 | UNKNOWN | PENDING | UNKNOWN | PENDING | PENDING | NO |
| E13 | UNKNOWN | PENDING | UNKNOWN | PENDING | PENDING | NO |

When verified: update the `Severity` line of that rule **and** this table. If any proposed OK script does not compile, repair the pair, update the fixture file/hash, and repeat. Never mark it as passed merely because an offline validator accepted it.

---

# Remaining diagnostic catalog — documented candidates, not approved errors

The sections below cover every remaining E00–E15 and W01–W10 ID from `BLUEPRINT.md` v1.1. They are **implementation notes and illustrative fragments**, not complete, verified fixtures. Until the owner provides passing/failing `.pine` files and a dated Pine Editor result, use `warning` or disable the rule. Avoid emitting diagnostics for a case that cannot be proven from the AST/signature metadata. A one-line fragment cannot be pasted into the Pine Editor as a complete program.

## E00 — Third-party parser rejection

- **Severity:** warning
- **Evidence status:** Parser behavior tested in the local checker; official compiler verdict unavailable.
- **Flags:** `pynescript` fails to parse source or raises a recognized parsing exception.
- **Does not flag:** Claiming the Pine Editor rejected it; oversized input rejected by application limits.
- **Message:** `pynescript could not parse this code: {reason}. Official compiler failure is unverified.`
- **Why:** An independent parser can reject valid future language syntax.
- **Reference:** [Checker contract in blueprint §9](../BLUEPRINT.md#9-the-checker)


**Illustrative problematic pattern (not a validated fixture):**

```pine
This is not Pine code.
```


**Implementation / verification notes:** Use parser-reported line/column when available. RecursionError/ValueError from the parser may lack a reliable location. Never make E00 trigger automated code repair based on compiler claims.



## E03 — Numeric expression used as a condition

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded. Severity note: warning pending fixture verification.
- **Flags:** Owner-known `int`/`float` passed to conditional tests where v6 requires `bool`.
- **Does not flag:** Unknown-type expressions or genuine `bool` expressions.
- **Message:** `if` conditions must be boolean in v6; compare the numeric value explicitly.
- **Why:** Pine v6 disallows implicit numeric-to-boolean casts.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
if bar_index
    label.new(bar_index, high, "x")
```


**Illustrative alternative (not compiler-verified):**

```pine
if bar_index > 0
    label.new(bar_index, high, "x")
```


**Implementation / verification notes:** These are fragments. Do not infer types from arbitrary variable names. Create a complete indicator pair before assigning error severity.



## E04 — Boolean NA values and functions

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded. Severity note: warning pending fixture verification.
- **Flags:** Explicit `bool` assignment from `na`, or `na()/nz()/fixnan()` used on a confidently typed boolean.
- **Does not flag:** Float or integer values where `na()` and related functions are allowed.
- **Message:** A boolean cannot be `na` in v6. Use `true` or `false`.
- **Why:** v6 booleans have only true and false states.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
var bool active = na
```


**Illustrative alternative (not compiler-verified):**

```pine
var bool active = false
```


**Implementation / verification notes:** These are fragments. Only flag `na(flag)` when the type of `flag` is definitely bool.



## E05 — Historical indexing of literals

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded. Severity note: warning pending fixture verification.
- **Flags:** Direct `[]` history referencing on a literal or prohibited constant.
- **Does not flag:** History references on valid series such as `close[1]`.
- **Message:** Do not access history on a literal; apply history to a valid series expression.
- **Why:** Pine v6 disallows history references on literal values.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
x = true[1]
```


**Illustrative alternative (not compiler-verified):**

```pine
x = close[1] > open[1]
```


**Implementation / verification notes:** Only `[]` directly attached to a known prohibited literal should trigger the rule.



## E06 — History of UDT fields directly

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded. Severity note: warning (type proof required).
- **Flags:** `[]` indexing of a user-defined-type field when the left-hand object is known to be a UDT instance.
- **Does not flag:** Unknown-type attributes, namespace access, legal history of the UDT object itself.
- **Message:** Reference the historical UDT object before accessing its field.
- **Why:** The v6 migration guide restricts direct field-history syntax.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
obj.field[1]
```


**Illustrative alternative (not compiler-verified):**

```pine
(obj[1]).field
```


**Implementation / verification notes:** These are schematic fragments, not complete test scripts. Do not flag until symbol/type inference is reliable.



## E07 — Duplicate named arguments

- **Severity:** warning
- **Evidence status:** Original examples written by Claude Code for this project (M3); **UNVERIFIED**. Pine Editor results NOT TESTED. The owner may change the severity to `error` only after recording evidence.
- **Flags:** A named argument that appears more than once in the same call, reported at the repeated argument.
- **Does not flag:** The same name in two separate calls; positional arguments.
- **Why:** BLUEPRINT §9.3 lists a repeated named argument as E07. Not yet confirmed in the Pine Editor.
- **Message (template):** `{argument}` is passed more than once to {call}. Keep one.
- **Coverage:** Any call. `{call}` is the function name with `()`, or `this call` when the callee has no plain name.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)
- **Bad fixture:** `tests/fixtures/E07_bad.pine` — expected finding line **3**, column **25**.
- **OK fixture:** `tests/fixtures/E07_ok.pine` — no finding expected.
- **Pine Editor:** **NOT TESTED** for both files. Compiles? `UNKNOWN`; first error (verbatim), editor line and date: `PENDING`.
- **Fixture SHA-256 (LF):** bad `7925ec74dc996790c52138bbfcafdbbee9a38d42f02182ad38455c8f0d38e46c`; ok `1a4b12c65149f93c0144afffeea5a380a7b59f5121f7848df617895a7d2ede1e`.



## E08 — Non-positive plot line width

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded. Severity note: warning pending fixture verification.
- **Flags:** A statically known `linewidth` less than 1 on an applicable function.
- **Does not flag:** Nonconstant values, functions for which the parameter has different semantics.
- **Message:** Set `linewidth` to an allowed positive number.
- **Why:** The v6 migration guide requires positive line widths for applicable visuals.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
plot(close, linewidth=0)
```


**Illustrative alternative (not compiler-verified):**

```pine
plot(close, linewidth=1)
```



## E09 — NA in parameters requiring unique constants

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded. Severity note: warning (semantic/type inference required).
- **Flags:** `na` where a fixed enum-like built-in constant is required, such as a plot style.
- **Does not flag:** `na` in a series parameter where it is allowed.
- **Message:** Supply a supported named style or an explicit legal default.
- **Why:** Pine v6 no longer accepts `na` for certain unique parameter types.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
plot(close, style=na)
```


**Illustrative alternative (not compiler-verified):**

```pine
plot(close, style=plot.style_line)
```


**Implementation / verification notes:** The missing-default `if`/`switch` case is more complex and should not ship without type-qualified evidence.



## E10 — Local request with dynamic requests disabled

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded. Severity note: warning pending fixture verification.
- **Flags:** A `request.*` call in a local block or function that is disallowed when `dynamic_requests=false`.
- **Does not flag:** Global requests or scripts with dynamic requests enabled.
- **Message:** Enable dynamic requests or restructure the request.
- **Why:** v6 permits dynamic requests by default but forbids certain local uses when explicitly disabled.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
indicator("X", dynamic_requests=false)
if close > open
    x = request.security(syminfo.tickerid, "D", close)
```


**Illustrative alternative (not compiler-verified):**

```pine
indicator("X")
if close > open
    x = request.security(syminfo.tickerid, "D", close)
```


**Implementation / verification notes:** These snippets are illustrative and require complete, parser-compatible fixtures.



## E11 — Legacy function names

- **Severity:** warning
- **Evidence status:** Original examples written by Claude Code for this project (M3); **UNVERIFIED**. Pine Editor results NOT TESTED. The owner may change the severity to `error` only after recording evidence.
- **Flags:** A call to `study`, `security`, `iff`, `tostring` or `tonumber` by its bare name, reported at the call.
- **Does not flag:** A function the script defines itself with one of these names; calls through a namespace, library alias or variable, such as `str.tostring()`, `lib.security()` or `x.tostring()`.
- **Why:** BLUEPRINT §9.3 lists these names and their v6 replacements. Not yet confirmed in the Pine Editor.
- **Message (template):** {function}() is not available in Pine v6. Use {replacement} instead.
- **Replacements (§9.3):** `study` → `indicator()`; `security` → `request.security()`; `iff` → the `?:` operator; `tostring` → `str.tostring()`; `tonumber` → `str.tonumber()`.
- **Reference:** [Blueprint §9.3](../BLUEPRINT.md#93-rules)
- **Bad fixture:** `tests/fixtures/E11_bad.pine` (`tostring`) — expected finding line **3**, column **12**.
- **Bad fixture:** `tests/fixtures/E11_bad_tonumber.pine` — expected finding line **3**, column **8**.
- **Bad fixture:** `tests/fixtures/E11_bad_iff.pine` — expected finding line **3**, column **9**.
- **Bad fixture:** `tests/fixtures/E11_bad_security.pine` — expected finding line **3**, column **13**.
- **Bad fixture:** `tests/fixtures/E11_bad_study.pine` — expected finding line **2**, column **0**. E15's missing-declaration warning is suppressed for this script because this finding already explains it.
- **OK fixture:** `tests/fixtures/E11_ok.pine` — `str.tostring()`; no finding expected.
- **OK fixture:** `tests/fixtures/E11_ok_user_function.pine` — a script-defined `tostring()`; no finding expected.
- **Pine Editor:** **NOT TESTED** for all seven files. Compiles? `UNKNOWN`; first error (verbatim), editor line and date: `PENDING`.
- **Fixture SHA-256 (LF):** bad `65ee4a732bb05d5239129b9b3c98db31e0fe550a093a72a98641a1a1a8d564d1`; bad_tonumber `b970663767ec2a1f2028e3c4e171f95021d92a275486cc31e60de8147abfaab6`; bad_iff `f724d1e256e82422aae29f9b0f1872f7bc5ada6a650e978f011cdbfff55b6c4a`; bad_security `2a5d9d25321b66ddeebe4a129b3ed3964f36205f90de739a08a506929ae5a62f`; bad_study `d52daff632346f643efa4823f63dd00c4cb3be70408582cebf022c2d52c500df`; ok `aadd76e1565c464daac1df439f7dacaa30407184fb7239495e40b127c9eb6c5e`; ok_user_function `785d78415f32cc3b2513d0794b474e47189f158a5dec91501b1efaa11a1cc1c2`.



## E12 — Unknown built-in names or parameters

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded. Severity note: warning; error only after complete signatures and manual proof.
- **Flags:** A built-in name absent from an explicitly complete namespace, or a named argument absent from a function whose `params_complete=true`.
- **Does not flag:** Variable methods, user-defined functions, imported libraries, or names in incomplete namespaces.
- **Message:** Use a supported function or parameter from the owner-approved signature list.
- **Why:** An incomplete catalog must never be treated as a complete list of built-in names.
- **Reference:** [Blueprint §9.5](../BLUEPRINT.md#95-made-up-names-e12)


**Illustrative problematic pattern (not a validated fixture):**

```pine
x = ta.smaa(close, 14)
```


**Illustrative alternative (not compiler-verified):**

```pine
x = ta.sma(close, 14)
```


**Implementation / verification notes:** Do not enable until `data/signatures.json` exists and relevant namespace/parameter completeness is independently established. `ta.smaa` is a candidate typo, not a confirmed compiler result.



## E14 — Missing v6 version annotation

- **Severity:** warning
- **Evidence status:** Original examples written by Claude Code for this project (M3); **UNVERIFIED**. Pine Editor results NOT TESTED. This is version compliance for the project's v6 target, not a confirmed compile error.
- **Flags:** No `//@version=` comment anywhere in the script, or one whose version is not 6. Reported at line 1, column 0.
- **Does not flag:** `//@version=6` on any line, including after the first statement, which pynescript itself does not report; spacing inside the comment that pynescript's comment parser accepts, such as `// @version = 6`. Text inside a string literal is never read as a version comment.
- **Why:** BLUEPRINT v1.1 §9.3–9.4 treat E14 as a version-compliance warning. The owner reports that TradingView's documentation allows the version annotation anywhere in the script; not yet confirmed in the Pine Editor.
- **Message (template), missing:** Add `//@version=6`: this project targets Pine v6. This is a compliance warning, not a confirmed compile error.
- **Message (template), other version:** `//@version={version}` is not Pine v6. Use `//@version=6`; this is a compliance warning, not a confirmed compile error.
- **Reference:** [Script structure](https://www.tradingview.com/pine-script-docs/language/script-structure/)
- **Bad fixture:** `tests/fixtures/E14_bad.pine` (no annotation) — expected finding line **1**, column **0**.
- **Bad fixture:** `tests/fixtures/E14_bad_v5.pine` (`//@version=5`) — expected finding line **1**, column **0**.
- **Bad fixture:** `tests/fixtures/E14_bad_string.pine` (the annotation text only inside a string) — expected finding line **1**, column **0**.
- **OK fixture:** `tests/fixtures/E14_ok.pine` — annotation on line 1; no finding expected.
- **OK fixture:** `tests/fixtures/E14_ok_late.pine` — annotation after the first statement; no finding expected.
- **Pine Editor:** **NOT TESTED** for all five files. Compiles? `UNKNOWN`; warnings, editor line and date: `PENDING`.
- **Fixture SHA-256 (LF):** bad `5f038ffd28bde4961d44f032c888cc40139f272589f2e0d760e03a6ff8e55d04`; bad_v5 `e75da140c8b5d5c1a08c0d848b727d1950199ce3d8b2003fec91bac6954306c4`; bad_string `8dd83fc3f803b4729ce4e573985df68fe5850def832cc6ab426fd100c9a382a3`; ok `9338ae6f2b5b4cabed7a6411d273a3cd8b508a112680952ca113657afa9c774e`; ok_late `b9e75a9bed94ecb7c9d7006b07f38bdc9fe3e4c1f6a82f02ebb9d3d28403f4d8`.



## E15 — Missing or incompatible script declaration

- **Severity:** warning
- **Evidence status:** Original examples written by Claude Code for this project (M3); **UNVERIFIED**. Pine Editor results NOT TESTED. The owner may change the severity to `error` only after recording evidence.
- **Flags:** (1) No top-level `indicator()`, `strategy()` or `library()` call; a declaration inside a local block does not count. Reported at line 1, column 0. (2) Any further declaration call once a top-level one exists, reported at that call. (3) `strategy.entry()` in a script whose top-level declaration is `indicator()`, reported at the call.
- **Does not flag:** A single top-level declaration; `strategy.entry()` under `strategy()`; the missing-declaration case when the script calls the legacy `study()`, which E11 already reports. `study()` is not counted as a declaration.
- **Why:** BLUEPRINT §9.3 lists a missing or repeated declaration and strategy order calls in an indicator as E15. Not yet confirmed in the Pine Editor.
- **Coverage:** Order-call misuse is limited to `strategy.entry()` (owner decision P-2); the other order functions need their own examples first.
- **Message (template), missing:** No top-level indicator(), strategy() or library() declaration. Add exactly one at the top level.
- **Message (template), duplicate:** Only one indicator(), strategy() or library() declaration is allowed. Remove this one.
- **Message (template), strategy call in indicator:** {function}() requires a strategy() declaration, but this script is an indicator().
- **Reference:** [Script structure](https://www.tradingview.com/pine-script-docs/language/script-structure/)
- **Bad fixture:** `tests/fixtures/E15_bad.pine` (no declaration) — expected finding line **1**, column **0**.
- **Bad fixture:** `tests/fixtures/E15_bad_local.pine` (declaration only inside an `if`) — expected finding line **1**, column **0**.
- **Bad fixture:** `tests/fixtures/E15_bad_two.pine` (two top-level declarations) — expected finding line **3**, column **0**.
- **Bad fixture:** `tests/fixtures/E15_bad_order.pine` (`strategy.entry()` under `indicator()`) — expected finding line **4**, column **4**.
- **OK fixture:** `tests/fixtures/E15_ok.pine` — the same call under `strategy()`; no finding expected.
- **Pine Editor:** **NOT TESTED** for all five files. Compiles? `UNKNOWN`; first error (verbatim), editor line and date: `PENDING`.
- **Fixture SHA-256 (LF):** bad `d08489e48c2a59716f11ad0fa17e290e068a0be01a9322c1b4961ebfd9c01c3f`; bad_local `7f23cf33d3646b406c8207cd82d38c8c3fd30fba633422d6c072a94a3e05f05d`; bad_two `c43c69fcf09c3f77ac4db78b600d3ea70b1a2b525c0de9ad2f9f901f7935a841`; bad_order `09e69115f0c1085685ee804364a2cf224ff79f7c8b487eea6569423c643a58ac`; ok `5dfc3f5ee16a11028610214e019050b4fdcd67f1b59f4892342143f11e7f627b`.



---

# Behavioral / migration warnings (W01–W10)

These are **warnings**, not compilation failures. The checker must not trigger automatic code repair solely because one appears. Some require type or data-flow analysis; when that proof is unavailable, leave the rule disabled or return an explicitly uncertain diagnostic.

## W01 — Constant integer division

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded.
- **Flags:** A known constant-int division expression whose v6 fractional result differs from v5 expectations.
- **Does not flag:** Division involving series floats or already intentional fractional arithmetic.
- **Message:** Division of constant integers may produce a fractional result in v6.
- **Why:** This can change calculations without causing a compiler error.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
ratio = 5 / 2
```


**Illustrative alternative (not compiler-verified):**

```pine
ratio = 2.5
```


**Implementation / verification notes:** Not every integer division is a bug. Warn only when it is useful as a migration review note.



## W02 — Changed default colors or label text color

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded.
- **Flags:** Relevant specific named colors or a label with implicit text color where migration behavior could differ.
- **Does not flag:** Explicitly supplied colors known to be intentional.
- **Message:** Review the updated palette and label defaults in v6.
- **Why:** Pine v6 adjusted some colors and default text color behavior.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
label.new(bar_index, high, "Signal")
```


**Illustrative alternative (not compiler-verified):**

```pine
label.new(bar_index, high, "Signal", textcolor=color.black)
```


**Implementation / verification notes:** This is not a compile error. The label call may be fine as written; the second fragment shows an explicit choice, not a universal fix.



## W03 — Changed default strategy margins

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded.
- **Flags:** A `strategy()` declaration without explicit margin settings when migrating old behavior.
- **Does not flag:** Strategies whose defaults are intentionally accepted.
- **Message:** Pine v6 defaults long and short margin percentages to 100; review assumptions.
- **Why:** Backtest behavior can change even when code compiles.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
strategy("Example")
```


**Illustrative alternative (not compiler-verified):**

```pine
strategy("Example", margin_long=100, margin_short=100)
```


**Implementation / verification notes:** The explicit 100 values preserve v6 defaults, not necessarily old behavior. The owner must select intended assumptions.



## W04 — Large-order history trimming

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded. Severity note: warning in answer text only; no checker rule.
- **Flags:** Strategies that may exceed the historical trade record limit, established by requirements or observed performance.
- **Does not flag:** Predicting actual order count from static source alone.
- **Message:** Very long-running strategies may have old trades trimmed instead of raising an error.
- **Why:** The number of executed trades depends on runtime data.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Implementation / verification notes:** Do not insert W04 into `RULES`. Mention it only if the user asks about order history or the context justifies it.



## W05 — Combined absolute/relative strategy exits

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded.
- **Flags:** `strategy.exit()` mixes related absolute and relative stop/limit/profit/loss inputs.
- **Does not flag:** A single clear exit target or intentionally combined logic documented by the user.
- **Message:** Check which specified exit level takes effect first in v6.
- **Why:** v6 changed how absolute and relative exit levels interact.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
strategy.exit("Exit", "Long", limit=close + 10, profit=20)
```


**Illustrative alternative (not compiler-verified):**

```pine
strategy.exit("Exit", "Long", profit=20)
```


**Implementation / verification notes:** The second fragment is an illustrative simplification, not a recommended trading exit policy. Do not infer user intent.



## W06 — Daily timeframe string changed

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded.
- **Flags:** Exact comparison such as `timeframe.period == "D"` where v6 returns a multiplier-prefixed string.
- **Does not flag:** Comparisons already expecting `"1D"` or user logic unrelated to timeframe.period.
- **Message:** On a daily chart Pine v6 reports `"1D"`; update the comparison.
- **Why:** A valid code path can silently stop firing after migration.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
isDaily = timeframe.period == "D"
```


**Illustrative alternative (not compiler-verified):**

```pine
isDaily = timeframe.period == "1D"
```


**Implementation / verification notes:** This detects a narrow literal comparison; do not claim that every use of `timeframe.period` is wrong.



## W07 — Lazy boolean evaluation of stateful calls

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded.
- **Flags:** A stateful series function is evaluated conditionally on the right of `and`/`or`.
- **Does not flag:** Pure functions and operands without stateful-history dependence.
- **Message:** Move the stateful calculation outside the short-circuit expression when necessary.
- **Why:** Pine v6 uses lazy evaluation for boolean operators.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative problematic pattern (not a validated fixture):**

```pine
signal = condition and ta.crossover(close, ta.sma(close, 20))
```


**Illustrative alternative (not compiler-verified):**

```pine
crossed = ta.crossover(close, ta.sma(close, 20))
signal = condition and crossed
```


**Implementation / verification notes:** Only warn when the called function is known to depend on consistent per-bar evaluation. The first snippet is schematic.



## W08 — Dynamic `for` boundaries

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded.
- **Flags:** A loop with an end bound that is modified during its own iteration.
- **Does not flag:** Loops with a constant or unchanged bound.
- **Message:** Pine v6 re-evaluates `for` loop limits during execution.
- **Why:** Changing the bound can change how many iterations run.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Implementation / verification notes:** Requires local data-flow analysis; do not flag every `for` loop. Full, verified loop fixtures are required.



## W09 — Nested dynamic requests

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded.
- **Flags:** Results of a request used inside another request where v6 dynamic execution may alter behavior.
- **Does not flag:** Independent requests without relevant nesting or behavior change.
- **Message:** Review dynamic request execution and compare against intended results.
- **Why:** Dynamic requests are available by default in v6.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Implementation / verification notes:** No reliable generic rewrite exists. Require owner-reviewed examples; do not silently change `dynamic_requests` settings.



## W10 — Negative array indices in v6

- **Severity:** warning
- **Evidence status:** Owner verification not yet recorded. Severity note: warning (migration information only).
- **Flags:** Relevant use of negative indexes in array.get/set/insert/remove when reviewing migration compatibility.
- **Does not flag:** Treating a valid negative index as a v6 syntax error.
- **Message:** Negative indexing can be valid in v6; check the intended element.
- **Why:** v6 permits certain negative array indexes.
- **Reference:** [v6 migration guide](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/)


**Illustrative alternative (not compiler-verified):**

```pine
last = array.get(values, -1)
```


**Implementation / verification notes:** This is an intentionally valid v6 pattern, not a bad example. The checker should not warn unconditionally in ordinary v6 code; use only migration context.



---

## Research-only public code references

These links support developer research and code-library design. They are **not** the six original M2 fixtures, not verified compilation results, and not authorization to copy or ingest the source. A GitHub repository's top-level license does not necessarily cover vendored files or every dependency. Inspect the specific file and applicable platform rules before any reuse.

| Research example | Concepts to study | Link | Initial reuse status |
| --- | --- | --- | --- |
| Higher-timeframe EMA | MTF, non-repainting logic | [davlacombe-collab — MTF EMA](https://github.com/davlacombe-collab/pine-scripts/blob/main/mtf-ema-non-repainting.pine) | Research only; not imported |
| ATR-based strategy template | Stops, position sizing, targets | [davlacombe-collab — risk template](https://github.com/davlacombe-collab/pine-scripts/blob/main/strategy-template-risk.pine) | Research only; not imported |
| Webhook alert example | Confirmed-bar signals and alerts | [davlacombe-collab — alerts](https://github.com/davlacombe-collab/pine-scripts/blob/main/alert-engine-webhook.pine) | Research only; not imported |
| SMC structure | Market structure and confluence | [casoon — SMC structure](https://github.com/casoon/pine-scripts) | Research only; complexity exceeds initial fixture scope |
| MTF S/R zones | Support and resistance | [casoon — indicator catalog](https://github.com/casoon/pine-scripts/blob/main/CATALOG.md) | Research only; not imported |
| Trend indicator | EMA, trend scoring | [casoon — indicator catalog](https://github.com/casoon/pine-scripts/blob/main/INDICATORS.md) | Research only; not imported |
| Existing offline Pine linter | Checker architecture and diagnostics | [folknor/pine-tools](https://github.com/folknor/pine-tools) | Study implementation and license notices only |

Scripts genuinely selected for reuse belong in `kb/scripts/` with owner-approved provenance metadata in `data/script_catalog.json` (blueprint §8), **not** embedded as unreviewed GitHub code in `docs/rules.md`.

## Owner checklist before M2 rule implementation

- [ ] Review the six original fixture files and confirm each expresses only its intended rule.
- [ ] Manually compile each of the three `*_bad.pine` and three `*_ok.pine` files in Pine Editor if legally permitted for the intended evaluation use.
- [ ] Replace all `NOT TESTED`, `UNKNOWN`, and `PENDING` entries with the **actual** observed results and dates.
- [ ] If a test script needs a correction, edit the matching fixture, update its displayed snippet and SHA-256, and retest.
- [ ] Approve the exact function coverage and the diagnostic message for E01, E02 and E13.
- [ ] Change a severity from `warning` to `error` **only** for verified, narrowly supported cases.
- [ ] Review and approve the examples for use in your repository. Then ask Claude Code to implement E01/E02/E13, one rule at a time, without changing the verified fixtures.
- [ ] Leave the frozen `eval/golden/` and `labels/pine_editor.csv` untouched. These fixtures are not part of the frozen benchmark.
