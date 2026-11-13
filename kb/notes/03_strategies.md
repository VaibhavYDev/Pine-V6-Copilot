# Basic strategy construction

## Strategy versus indicator
Use `strategy(...)` to produce order simulations; use `indicator(...)` for visual studies. A strategy can plot indicators too, but an indicator must not call strategy-only order functions.

## Entering on an event
Declare a Boolean signal such as `goLong = ta.crossover(fast, slow)` on every bar. Use `if goLong` followed by a call to `strategy.entry(...)` to request a simulated order.

## Exiting with stop and limit
`strategy.exit(...)` can define stop and limit prices for a named entry. Explicitly distinguish price levels from tick distances. Validate that the exit identifiers refer to intended entries.

## ATR-based protective levels
A long position's illustrative stop can be `strategy.position_avg_price - atrMultiple * atrValue`. A target can be above the average entry price. Any moving ATR reference can cause levels to change over time, so explain whether the levels should be fixed or trailing.

## Order quantity assumptions
Do not guess quantity, leverage, commissions, slippage, stop distances, or execution assumptions from a vague user request. Ask for material missing inputs or disclose the assumptions clearly.

## Backtests are simulations
TradingView backtests depend on bar data, fill assumptions, fees, lookahead, instrument specifications, and history. A strategy compiling successfully does not validate profitability or practical execution quality.
