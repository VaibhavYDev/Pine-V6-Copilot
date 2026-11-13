# Pine v6 language migration

## Version annotation
Use `//@version=6` when the requested output targets Pine v6. Keep the annotation near the beginning for readability. A missing annotation does not itself prove a compiler failure; versions must be interpreted according to the language rules.

## Script declarations
A complete standalone indicator begins with `indicator(...)`, a strategy with `strategy(...)`, or a library with `library(...)`. One valid global declaration describes the script. `study(...)` is a legacy form, not the v6 declaration to generate.

## Boolean conditions
Conditions in v6 require Boolean expressions. For example, write `if bar_index > 0` rather than relying on an integer to behave as a Boolean. This applies to entry guards and alert logic.

## Boolean `na` migration
In v6 a Boolean is not `na`. Code that previously treated `na`, `true`, and `false` as three Boolean states should represent the third state explicitly with an integer or another type instead.

## Removed strategy `when` parameter
Do not pass `when=` to `strategy.entry(...)` or the other applicable v6 order functions. Calculate a Boolean condition and place the order call inside an `if` block.

## Removed `transp` parameter
The former `transp=` parameter has been removed. Use `color.new(baseColor, transparency)` for a color with transparency, e.g. `plot(close, color=color.new(color.blue, 50))`.

## Duplicate function arguments
Pass each named parameter only once in a function call. Providing the same named argument twice is invalid; a parser may still produce an AST that a deterministic checker must inspect.

## Constant integer division
In Pine v6, `5 / 2` can produce `2.5`. Do not assume the older integer-truncating behavior. Use an explicit conversion or rounding only when the intended behavior calls for it.

## Timeframe strings
The `timeframe.period` value now includes a multiplier, e.g. `"1D"` rather than `"D"`. Compare timeframe strings carefully; a false comparison may produce no compiler error.
