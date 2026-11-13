# Checker and compiler diagnostics

## Static analysis is not compilation
The project's Python checker reports locally defined patterns. An empty findings list does not mean the Pine Editor will compile a script; only an actual compiler result can establish that for a specific version of the code.

## Parser uncertainty
An E00 finding means the offline parser could not reliably inspect the source. It is not a confirmed TradingView compiler error and should not automatically trigger a repair.

## Provisional warnings
Until the owner records compiler evidence, the known E01, E02, E07, E11, E13, E14 and E15 patterns remain provisional warnings. They should be displayed without inventing precision or recall scores.

## Unknown functions
A missing entry in an incomplete function-signature list is not proof of a fabricated Pine function. The list must declare a namespace complete before a missing function in that namespace can be judged definitively.

## Source-provenance checks
A retrieved example is a reference, not automatic permission to reuse or confirmation it meets trader requirements. Preserve source identification and review status; altered code loses any prior compiler-verification status.

## Requirement coverage is separate
A script can pass static syntax checks yet omit a requested stop-loss, alert, or indicator parameter. Record supported, missing and uncertain trading requirements separately when the requirement-aware product mode is implemented.
