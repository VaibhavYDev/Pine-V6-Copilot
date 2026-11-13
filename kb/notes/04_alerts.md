# Alert design

## Global alertcondition
`alertcondition(condition, title, message)` registers a selectable alert condition in an indicator. Its call belongs at global scope; calculate the condition first and pass the Boolean series.

## Bar-close confirmation
Signals that use the current unclosed candle can change until that candle closes. When stable close-based signals are required, consider an explicit confirmed-bar condition and describe its timing impact.

## One alert per event
Avoid creating an alert on every bar merely because a condition stays true. Edge-triggered events such as `ta.crossover(...)` and `ta.crossunder(...)` often fit entry/exit alert requests more closely.

## Alerts do not execute trades
Creating Pine alert definitions does not connect a broker or guarantee execution. Webhook consumers, duplicate alerts, delays, and exchange-specific behavior require separate operational controls.
