# Cost-controlled setup before any live model request

This guide is for the project owner. No provider API call has been made while preparing this package. **Neither the checked-in API nor the existing pipeline enforces a daily budget yet**; that control belongs to the planned M8 endpoint. `DAILY_TOKEN_BUDGET` as an environment variable is not by itself an active limit.

## Groq writer

1. Open https://console.groq.com/ and use a separate project and API key for Pine v6 Copilot if available on your account.
2. Check the current model IDs and quotas in your own console. Set `CHAT_MODEL` to the exact supported model you choose, not an invented placeholder.
3. For an eligible **paid** Groq organization owner, navigate **Settings → Billing → Limits** and set a modest **monthly organization-wide spending limit** plus notification thresholds. If that control is unavailable on your tier, use free-tier restrictions and do not assume you have a hard monetary cap.
4. Groq says spending accounting can lag around 10–15 minutes; limit API requests yourself during any initial test.

## Gemini embeddings and judge

1. Open https://aistudio.google.com/ and use a dedicated API project and key for Gemini embedding and judge access.
2. Check project model availability and quotas. The blueprint uses `gemini-embedding-001` with 768 output dimensions; its `task_type` values are `RETRIEVAL_DOCUMENT` and `RETRIEVAL_QUERY`. Do not switch to a different embedding model without re-embedding the whole database.
3. If billed, visit the **Spend** page in AI Studio and set the experimental project **monthly spend cap**, where available. If using prepaid billing, start with the smallest suitable balance, keep automatic reload disabled unless intentionally approved, and understand any project/account caps.
4. Gemini spend-cap enforcement and billing updates may lag around 10 minutes, so this is not an instantaneous guaranteed hard stop.

## Local credentials and database

- Never send keys to ChatGPT or Claude Code, paste keys into GitHub Issues, or commit them.
- The current code reads environment variables from the process, not automatically from `.env`. The original `.env` is git-ignored and Claude Code is restricted from reading it.
- Populate `CHAT_BASE_URL`, `CHAT_MODEL`, `CHAT_API_KEY`, `JUDGE_BASE_URL`, `JUDGE_MODEL`, `JUDGE_API_KEY`, `GEMINI_API_KEY`, `EMBED_MODEL`, `EMBED_DIM=768`, `DATABASE_URL`, and `KB_DIR` only as needed for the specific operation.
- Use `127.0.0.1` instead of `localhost` in the Windows PostgreSQL URL if local name resolution is slow.
- Do not run `python -m ingest` until you approve the corpus and authorize the Gemini embedding charge. Ingestion may send more than one request and is NOT a safe dry run.
- For a **one-call writer probe** use the review helper after explicitly choosing and configuring a permitted model. It prints metadata, not keys or the raw reply.
- Do not open a public `/ask` endpoint until M8's atomic reservation, rate limiting, request caps, retention notices, and the isolated parser timeout are actually implemented and tested.

## Sources for current controls (review at time of setup)

- Groq spend limits: https://console.groq.com/docs/spend-limits
- Groq project limits: https://console.groq.com/docs/projects
- Gemini API billing and spend caps: https://ai.google.dev/gemini-api/docs/billing
- Gemini embeddings: https://ai.google.dev/gemini-api/docs/embeddings
