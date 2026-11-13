# Pine v6 Copilot

A Pine Script v6 assistant in early development. It is planned in three parts:

- a checker that reads a Pine script and lists v6 problems, offline and without a model;
- an assistant that looks up notes and function signatures, asks a model to write the answer, runs the checker and asks for a fix when needed;
- an evaluation that runs hand-written tasks through the assistant and compares the results with TradingView's Pine Editor, checked by hand.

## Status

Implemented and tested locally:

- **Static checker** (`checker/`): input limits, parsing with pynescript, and seven provisional rules (E01, E02, E07, E11, E13, E14 and E15), plus E00 for code the parser cannot read. The rules and their test scripts are documented in [docs/rules.md](docs/rules.md). None of the rules has been confirmed in TradingView's Pine Editor yet, so every finding is a warning, not a confirmed compile error.
- **Check page and `POST /check`** (`api/`): runs the checker on pasted code. No model is called and the code is not stored.
- **Retrieval** (`ingest/`, `retrieval/`): `python -m ingest` splits the knowledge base into chunks (one per note section, script and function signature), embeds new or changed chunks with `gemini-embedding-001` at 768 dimensions and stores them in Postgres with pgvector. `search(question)` returns the signature chunks for function names in the question, then the best chunks from full-text and vector search combined by Reciprocal Rank Fusion. It is tested against a real Postgres with a fake embedding function. Retrieval quality has not been measured.
- **Answer pipeline** (`pipeline/answer.py`, `prompts/`): `answer(question, code=None, retrieve=True, repair=True)` looks up references when retrieval is on, asks the writer model for a draft with the versioned prompts in `prompts/` and runs the checker on the script. It sends at most two repair requests, and only for findings with `error` severity; every rule is a warning today, so no repair is sent yet. It keeps the draft next to the selected script and reports each model call, token counts, timings and sources. A reply that was cut off, filtered or not confirmed complete is never returned as code. The pipeline is tested with fake model replies only: no live model call has been made and no endpoint uses it yet. A clean static check does not show that a script compiles or does what was asked.

A starter knowledge base is in `kb/` and `data/signatures.json`: 43 note sections, 10 example scripts and 31 function signatures. It was drafted with AI assistance and is waiting for the owner's review and approval. The signature list is partial, and none of the scripts has been tested in TradingView's Pine Editor. `review/script_verification.csv` records each script's SHA-256 and, once a script is tested, the result; the tests check that every recorded hash still matches its script. The knowledge base has not been ingested yet.

Still under development: the `/ask` endpoint and page, code reuse and the evaluation.

The app is for local development only. The parser has no hard time limit yet, so the service must not be exposed publicly.

## Run locally

You need Python 3.12. Docker is only needed for the database that retrieval uses.

```shell
py -3.12 -m venv .venv          # macOS/Linux: python3.12 -m venv .venv
.venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn api.app:app             # Check page on http://127.0.0.1:8000
```

`POST /check` takes `{"code": "<Pine Script source>"}` and returns `findings` (each with `rule`, `severity`, `line`, `col` and `message`; lines count from 1 and columns from 0), the `errors` and `warnings` counts, and a `note`. Empty code, or code over 40,000 characters, 800 lines or 50 levels of bracket nesting, gets HTTP 422.

The database for retrieval, set up once:

```shell
docker compose up -d db         # Postgres 16 with pgvector on 127.0.0.1:5432
docker compose cp db/schema.sql db:/tmp/schema.sql
docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 -f /tmp/schema.sql
```

`python -m ingest` loads `kb/notes/*.md`, `kb/scripts/*.pine` and `data/signatures.json` into that database. It reads `DATABASE_URL`, `GEMINI_API_KEY`, `EMBED_MODEL`, `EMBED_DIM` and `KB_DIR` from the shell environment (see `.env.example`; a `.env` file is not loaded). It embeds only new or changed chunks, so it calls the Gemini API, which can cost money, only when the files have changed.

The checks CI runs, with a database service:

```shell
ruff check .
python -m eval.freeze --check
pytest -q --require-db
```

The database tests only run against a local server. Each test run creates its own database, `pine_v6_copilot_test_` followed by a random suffix, and drops only that database when it ends, so no existing database is dropped. A test process that is killed can leave its database behind. Without a server the tests are skipped; `--require-db` makes them fail instead. To run them locally:

```shell
docker compose up -d db
$env:DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"   # macOS/Linux: export DATABASE_URL=...
pytest -q
```

On Windows, use `127.0.0.1` rather than `localhost` in `DATABASE_URL`: in testing, each connection through `localhost` waited for the full connection timeout before falling back to IPv4.

## License

MIT, see [LICENSE](LICENSE). Dependencies keep their own licenses. pynescript (LGPL-3.0-or-later) and psycopg (LGPL-3.0-only) are installed from PyPI and used unmodified.

## Notice

This project is not affiliated with, endorsed by or sponsored by TradingView. Pine Script® and TradingView® are trademarks of TradingView, Inc.
