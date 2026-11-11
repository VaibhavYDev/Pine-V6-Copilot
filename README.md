# Pine v6 Copilot

A Pine Script v6 assistant in early development. It is planned in three parts:

- a checker that reads a Pine script and lists v6 problems, offline and without a model;
- an assistant that looks up notes and function signatures, asks a model to write the answer, runs the checker and asks for a fix when needed;
- an evaluation that runs hand-written tasks through the assistant and compares the results with TradingView's Pine Editor, checked by hand.

## Status

Implemented and tested locally:

- **Static checker** (`checker/`): input limits, parsing with pynescript, and seven provisional rules (E01, E02, E07, E11, E13, E14 and E15), plus E00 for code the parser cannot read. The rules and their test scripts are documented in [docs/rules.md](docs/rules.md). None of the rules has been confirmed in TradingView's Pine Editor yet, so every finding is a warning, not a confirmed compile error.
- **Check page and `POST /check`** (`api/`): runs the checker on pasted code. No model is called and the code is not stored.

Still under development: retrieval (RAG), code generation, code reuse, automated repair and the evaluation.

The app is for local development only. The parser has no hard time limit yet, so the service must not be exposed publicly.

## Run locally

You need Python 3.12. Docker is only needed for the database that later features use.

```shell
py -3.12 -m venv .venv          # macOS/Linux: python3.12 -m venv .venv
.venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn api.app:app             # Check page on http://127.0.0.1:8000
```

`POST /check` takes `{"code": "<Pine Script source>"}` and returns `findings` (each with `rule`, `severity`, `line`, `col` and `message`; lines count from 1 and columns from 0), the `errors` and `warnings` counts, and a `note`. Empty code, or code over 40,000 characters, 800 lines or 50 levels of bracket nesting, gets HTTP 422.

The database for later features:

```shell
docker compose up -d db         # Postgres 16 with pgvector on 127.0.0.1:5432
```

The checks CI runs:

```shell
ruff check .
python -m eval.freeze --check
pytest -q
```

## License

MIT, see [LICENSE](LICENSE). Dependencies keep their own licenses. pynescript (LGPL-3.0-or-later) and psycopg (LGPL-3.0-only) are installed from PyPI and used unmodified.

## Notice

This project is not affiliated with, endorsed by or sponsored by TradingView. Pine Script® and TradingView® are trademarks of TradingView, Inc.
