# Timeframes and external series

## request.security basics
`request.security(syminfo.tickerid, timeframe, expression)` retrieves an expression evaluated in a specified chart context. The requested timeframe and symbol should be explicit rather than guessed.

## Higher timeframe selection
An indicator showing a higher-timeframe signal should document the relationship between the chart timeframe and requested timeframe. Avoid silently treating a lower requested timeframe as equivalent to a higher one.

## Lookahead behavior
`barmerge.lookahead_on` may expose future information on historical bars if used incorrectly. Offset confirmed higher-timeframe values when the design requires a non-lookahead historical series.

## Real-time repainting
A higher-timeframe bar can keep changing until it closes. Using `lookahead_off` alone does not guarantee that values observed in real time remain unchanged. Repainting behavior must be assessed explicitly for the intended signal.

## Dynamic requests in v6
Pine v6 supports dynamic `request.*()` operations by default. Setting `dynamic_requests=false` changes what request calls may do in local scopes. The desired mode is a script-level decision, not a reason to rewrite request logic blindly.
