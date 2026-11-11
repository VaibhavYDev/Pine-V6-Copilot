# Pine v6 Copilot

A Pine Script v6 assistant in early development. It is planned in three parts:

- a checker that reads a Pine script and lists v6 problems, offline and without a model;
- an assistant that looks up notes and function signatures, asks a model to write the answer, runs the checker and asks for a fix when needed;
- an evaluation that runs hand-written tasks through the assistant and compares the results with TradingView's Pine Editor, checked by hand.

## Status

Phase 0, the project skeleton: configuration loading, the database schema and search query, the task-freeze script, CI, and the Claude Code settings and hooks that protect the evaluation files. The checker rules, retrieval, generation, API and evaluation are not implemented yet.

## Run locally

You need Python 3.12 and Docker.

```shell
py -3.12 -m venv .venv          # macOS/Linux: python3.12 -m venv .venv
.venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
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
