# Pine v6 Copilot — starter knowledge base review

## Status and permission

This is an **original AI-drafted starter corpus prepared for owner review**. Nothing has been compiled or checked in TradingView's Pine Editor, and no script is labelled compiler-verified. No outside GitHub scripts or TradingView documentation passages were copied. Do not represent this as manually authored by the owner unless reviewed and edited accordingly.

**Hardening pass, 2026-11-13.** Claude Code corrected seven signature entries and revised scripts 02, 06, 07, 08, 09 and 10; both are listed below. The notes' content was not changed. Every script is still `NOT_TESTED` and `NOT_APPROVED`.

The notes are paraphrased explanations of general Pine v6 behavior. The signature records are **partial references**, not a complete copy of the function reference. `complete_namespaces` is intentionally empty. Only `ta.rsi` is marked `params_complete=true` because its two-parameter signature is explicitly provided in the project blueprint; all other entries are conservative. Validate return types, overloads, argument qualifiers, and named parameter spelling against current references before enabling E12 error findings.

## Placement

Extract the `kb/` and `data/` folders into the repository root alongside `BLUEPRINT.md`. Do **not** overwrite `BLUEPRINT.md`, `CLAUDE.md`, evaluation data, or previous user-authored content. Review any pre-existing `kb/` or `data/` entries before merging.

Expected paths: `kb/notes/*.md`, `kb/scripts/*.pine`, `data/signatures.json`. The project ingestion command reads exactly these paths. The files in `review/` are deliberately outside the ingested `kb/`.

## Mandatory approval sequence

1. Read the notes and scripts; correct any incorrect claims or trading assumptions.
2. Record each Pine Editor result in `review/script_verification.csv`: `verification_status`, `test_date`, `symbol`, `timeframe`, the exact `compiler_message` and `reviewer_notes` (quote a field that contains a comma). A result applies only to the `sha256` in its row: after any edit, record the new hash and set the row back to `NOT_TESTED`. `pytest tests/test_knowledge_base.py` fails when a recorded hash no longer matches its file. Do not mark a script verified without that evidence.
3. Set scripts' reuse rights and provenance separately when creating the future `data/script_catalog.json`; this package does not grant blanket reuse permission or mark any script approved.
4. Confirm `data/signatures.json` against authoritative function references, especially overloads. Keep `complete_namespaces=[]` until an entire namespace is verified.
5. First run an offline *read-only* preview of `ingest.read_chunks(Path("kb"), Path("data/signatures.json"))` in the project's Python environment. No provider keys or DB required for this preview.
6. Only after the provider spending controls have been configured and the user separately authorizes live ingestion, run `python -m ingest`. This generates paid or quota-consuming Gemini embeddings; do not run it as an exploratory dry run.

## Coverage

- 7 Markdown note files, 43 short note sections.
- 10 original Pine v6 illustrative scripts, all **unverified**.
- 31 partial function signature records; 0 complete namespaces.

## Human review references

These URLs are for a person to read; they are not scraped into the corpus.

- Pine v6 migration: https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/
- TradingView alerts: https://www.tradingview.com/pine-script-docs/concepts/alerts/
- TradingView arrays: https://www.tradingview.com/pine-script-docs/language/arrays/
- TradingView type system: https://www.tradingview.com/pine-script-docs/language/type-system/
- TradingView documentation home: https://www.tradingview.com/pine-script-docs/

## Important limitations

Static syntax checks can pass while the official Pine Editor rejects a script. Even scripts that compile may repaint or place simulated orders incorrectly. The generated code is educational and not a trading recommendation. Do not deploy publicly until parser timeouts, request-body limits, atomic budget reservations, rate limits, retention notices, provider limits and all other blueprint release gates are met.

## Optional review helpers

From the **project root** after extracting the ZIP, you can run the read-only corpus preflight without credentials, embeddings or database access:

```powershell
.\.venv\Scripts\python.exe -m review.offline_preflight
```

After you have configured provider-side spending controls and explicitly approve **one** live request, set the writer endpoint and model. Groq is shown; `config.py` also accepts Gemini's OpenAI-compatible URL. Then manually run:

```powershell
$env:CHAT_BASE_URL = "https://api.groq.com/openai/v1"
$env:CHAT_MODEL = "YOUR_APPROVED_MODEL_ID"
.\.venv\Scripts\python.exe -m review.one_live_finish_reason --authorize-one-live-call
```

The helper always asks for the writer key without showing or saving it, which keeps the key out of shell history, and removes it from the process afterwards. `config.py` checks the model, endpoint and key before anything is sent. It makes one `chat()` call with the pipeline's own limits (1,500 output tokens, 30 s timeout), so a `length` result means real drafts would be cut short too. The client may retry once after a 429, a 5xx or a timeout, so at most **two** provider requests are sent. It prints the model, `finish_reason`, token counts, request count and latency; it never prints the reply, the prompt or the key. It tests the writer endpoint only, not Gemini embeddings or the judge. `tests/test_one_live_finish_reason.py` checks this behavior against a fake provider. Do not run this command until you have personally authorized the call and checked the account caps.

## Signature corrections (2026-11-13)

No TradingView page was fetched or copied for these changes (BLUEPRINT section 4). The evidence is web-search results that summarize the TradingView pages linked below, knowledge of the reference, and third-party references where noted. Confirm each row marked "yes" by reading its entry in the [v6 Reference Manual](https://www.tradingview.com/pine-script-reference/v6/).

| Entry | Change | Evidence | Confirm |
| --- | --- | --- | --- |
| `map.put` | Returns `V`, the key's previous value or `na` for a new key (was `void`); summary updated | Owner instruction; a third-party Pine implementation documents the same return. The official entry was not seen | yes |
| `plotshape` | `series` is `series int/float/bool` (was `series bool`); summary mentions numeric series and `location.absolute` | [Visuals overview](https://www.tradingview.com/pine-script-docs/visuals/overview/): int, float and bool series | no |
| `input.float` | `defval` is `const int/float` (was `const float`) | [Inputs](https://www.tradingview.com/pine-script-docs/concepts/inputs/): int values are accepted where float is expected. The reference's exact notation was not seen | yes |
| `request.security` | `expression` is `series int/float/bool/color/string, object, collection or tuple`, and it returns `same type as expression` (both were `series value`, which is not a Pine type) | [Other timeframes and data](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/): tuples, and objects or collections that meet its type rules; v6 dynamic requests take `series string` symbol and timeframe | no |
| `ta.macd`, `ta.bb` | Return `[series float, series float, series float]` (was "tuple of three series float") | Third-party references; order MACD, signal, histogram and basis, upper, lower | yes |
| `plot` | Summary says "indicator or strategy", not the legacy "study" | Wording only | no |
| `ta.sma` length | Kept `series int` | [Type system](https://www.tradingview.com/pine-script-docs/language/type-system/) uses `ta.sma()` with a series length | no |
| `ta.highest`, `ta.lowest`, `ta.stdev`, `ta.bb` length | Kept `series int` | [Release notes](https://www.tradingview.com/pine-script-docs/release-notes/): series lengths from September 2020 (highest, lowest) and January 2021 (bb, stdev). No v6 page seen | yes |
| `ta.rsi` | Kept `params_complete: true`: `source`, and a `simple int` length | [Type system](https://www.tradingview.com/pine-script-docs/language/type-system/): `ta.rsi()` requires a simple length; BLUEPRINT section 8.2 | no |

`complete_namespaces` stays empty, and every entry except `ta.rsi` stays `params_complete: false`.

## Script revisions (2026-11-13)

- `02`: markers and alerts also require `barstate.isconfirmed`, so they appear only after the crossing bar closes. Historical bars are unchanged.
- `06`: comments state the `strategy()` defaults it relies on and when orders fill. The logic is unchanged.
- `07`: the stop and target are tick distances from the actual fill price, sized by the signal bar's ATR and fixed for the trade. The exit is sent with the entry, so it covers the bar the entry fills on. There is no entry before ATR has a value or while a position is open. Before, the levels moved with the current ATR and the fill bar had no exit order. Comments state the simulation limits.
- `08`: stops with a runtime error when the requested timeframe is below the chart's. Comments explain the realtime repainting and the `[1]` with `lookahead_on` alternative.
- `09`: the average is `na` until the window holds `lookback` closes; before, it averaged fewer values.
- `10`: counts up, down and unchanged bars by key and plots the share of up bars, showing that `map.get()` returns `na` for a missing key. Before, it plotted `close`.
