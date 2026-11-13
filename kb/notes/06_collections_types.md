# Collections and data structures

## Arrays
Arrays hold ordered elements of one supported type. `array.push(...)` appends and `array.get(...)` reads an element by index. Verify `array.size(...)` before accessing an index that may not exist.

## Array lifetime
A `var` array persists across bar calculations, while a freshly created array can be reinitialized on each execution. Long-running indicators should bound arrays when they only need recent observations.

## Maps
Maps associate keys with values. Use a declared key and value type such as `map<string, float>` and `map.put(...)` or `map.get(...)` for lookup. Do not assume an absent key returns a meaningful numeric value.

## User-defined types
A Pine `type` declaration groups named fields, e.g. `type RangeInfo` with `float highValue` and `float lowValue` fields. This is a language structure for data representation, not a trading signal by itself.

## Persistent variables
Use `var` for values intended to retain state between bars. Understand whether a value updates once per bar, intrabar, or with higher-timeframe data before building a stateful signal.

## History and warm-up
A historical reference such as `close[1]` may be unavailable at the start of a dataset. Handle early-bar `na` values with appropriate guards instead of assuming every bar has complete history.
