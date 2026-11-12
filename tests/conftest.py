import json
import re
import socket
import uuid
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

import config

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
FIXTURES = Path(__file__).parent / "fixtures"
TEST_DATABASE_PREFIX = "pine_v6_copilot_test_"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
LOCAL_SETUP = (
    "To run them, start the database with `docker compose up -d db` and set "
    "DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/postgres before running pytest."
)

NOTE = """# Test note

## Line colours
This section mentions color.new by name.

## Background
This section is about shading behind the bars.
"""
# BLUEPRINT 8.2.
RSI = {
    "params": [{"name": "source", "type": "series int/float"}, {"name": "length", "type": "simple int"}],
    "returns": "series float",
    "params_complete": True,
    "summary": "Relative strength index of source over length bars.",
}
# Not a Pine function: a bare name for the exact-lookup tests that claims nothing about real signatures.
PROBE = {"params": [], "returns": "nothing", "summary": "Synthetic record for tests."}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-db", action="store_true", help="fail the database tests, instead of skipping them, without PostgreSQL"
    )


@pytest.fixture(scope="session")
def admin_url(request: pytest.FixtureRequest) -> str:
    """DATABASE_URL, once it names a local server that answers. Otherwise skip, or fail with --require-db."""
    try:
        url = config.database_url()
        host = conninfo_to_dict(url).get("host")
        if host not in LOCAL_HOSTS:
            raise RuntimeError(f"tests only use a local server, and DATABASE_URL names {host!r}")
        psycopg.connect(url, connect_timeout=5).close()
    except (RuntimeError, psycopg.OperationalError) as error:
        message = f"PostgreSQL is unavailable: {error}. {LOCAL_SETUP}"
        if request.config.getoption("--require-db"):
            pytest.fail(message)
        pytest.skip(message)
    return url


@pytest.fixture(scope="session")
def test_database_url(admin_url: str) -> Iterator[str]:
    """A database created for this test session only, with db/schema.sql."""
    with temporary_database(admin_url, SCHEMA_FILE.read_text(encoding="utf-8")) as url:
        yield url


@contextmanager
def temporary_database(admin_url: str, schema: str) -> Iterator[str]:
    """A new database with a random name and `schema`, dropped on exit. No other database is ever dropped."""
    name = f"{TEST_DATABASE_PREFIX}{uuid.uuid4().hex}"
    with psycopg.connect(admin_url, autocommit=True, connect_timeout=5) as conn:
        # No "if not exists": a name that is already taken stops here, and that database is left alone.
        conn.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    try:
        url = make_conninfo(admin_url, dbname=name)
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(schema)
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=5) as conn:
            conn.execute(sql.SQL("drop database {} with (force)").format(sql.Identifier(name)))


@pytest.fixture
def database(test_database_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """The test database, with an empty chunks table, as DATABASE_URL."""
    with psycopg.connect(test_database_url, autocommit=True) as conn:
        conn.execute("truncate chunks restart identity")
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    return test_database_url


@pytest.fixture
def embed_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], str]]:
    """Replaces embed() with a fake that records each call. Only local hosts can be reached meanwhile."""
    calls: list[tuple[list[str], str]] = []

    def fake_embed(texts: list[str], task: str) -> list[list[float]]:
        calls.append((texts, task))
        return [word_vector(text) for text in texts]

    real_getaddrinfo = socket.getaddrinfo

    def local_only(host: object, *args: object, **kwargs: object) -> object:
        if host not in LOCAL_HOSTS:
            raise OSError(f"tests may not connect to {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr("llm.client.embed", fake_embed)
    monkeypatch.setattr(socket, "getaddrinfo", local_only)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EMBED_MODEL", "test-embedding-model")
    monkeypatch.setenv("EMBED_DIM", "768")
    return calls


def word_vector(text: str) -> list[float]:
    """Texts that share words point in similar directions. The first value keeps the vector from being all zeros."""
    vector = [1.0] + [0.0] * 767
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        vector[1 + zlib.crc32(word.encode()) % 767] += 1.0
    return vector


@pytest.fixture
def knowledge_base(tmp_path: Path) -> tuple[Path, Path]:
    """kb/ with a two-section note and a script, and a signatures file with ta.rsi and a synthetic name."""
    kb = tmp_path / "kb"
    (kb / "notes").mkdir(parents=True)
    (kb / "scripts").mkdir()
    (kb / "notes" / "test.md").write_text(NOTE, encoding="utf-8")
    script = (FIXTURES / "E01_ok.pine").read_text(encoding="utf-8")
    (kb / "scripts" / "entry.pine").write_text(f"// Test script built from the E01_ok fixture.\n{script}", encoding="utf-8")
    signatures = tmp_path / "data" / "signatures.json"
    signatures.parent.mkdir()
    functions = {"ta.rsi": RSI, "probe": PROBE}
    signatures.write_text(json.dumps({"complete_namespaces": [], "functions": functions}), encoding="utf-8")
    return kb, signatures
