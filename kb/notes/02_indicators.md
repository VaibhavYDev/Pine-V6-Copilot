# Common indicator patterns

## Moving averages
`ta.sma(source, length)` smooths values with equal weighting; `ta.ema(source, length)` gives more weight to recent observations. Keep length inputs positive and label plots clearly.

## EMA crossover signal
Compute both moving averages on every bar. A crossover signal can be expressed as `ta.crossover(fast, slow)`, while `ta.crossunder(fast, slow)` detects the opposite transition. These signal conditions should be evaluated consistently on each bar.

## RSI oscillator
`ta.rsi(close, length)` is a momentum measure, not a guarantee of reversal. It may lack meaningful values on early bars. A compact RSI pane uses `overlay=false` and threshold guides.

## MACD tuple
`ta.macd(close, fastLength, slowLength, signalLength)` returns a MACD line, signal line, and histogram. Destructure all three outputs before plotting or deriving signals.

## ATR volatility
`ta.atr(length)` measures recent trading ranges. It has price units, not percentage units. Multiplying ATR by a user-selected factor can set a volatility-distance estimate; it does not establish suitable risk for every instrument.

## Plot scope
Global plotting calls such as `plot()` and `plotshape()` should not be inside local `if` blocks. Calculate the value or Boolean condition in local logic as needed, then call the plot function at global scope.

## Transparency and backgrounds
For conditional shading, use a global `bgcolor(condition ? color.new(color.green, 90) : na)` call. Avoid obsolete `transp=` arguments.
