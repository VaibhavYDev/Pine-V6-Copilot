import re
from dataclasses import dataclass
from pathlib import Path

import psycopg

from config import database_url
from llm import client

SEARCH_SQL = (Path(__file__).resolve().parents[1] / "db" / "search.sql").read_text(encoding="utf-8")
EXACT_SQL = """
select id, source, heading, body, kind, symbols
from chunks
where kind = 'signature' and symbols && %(names)s;
"""
POOL = 20
MAX_EXACT_NAMES = 8
# Dotted names such as ta.rsi and bare words such as plot. Only those that are a signature's name match.
NAME = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")


@dataclass(frozen=True)
class RetrievedChunk:
    id: int
    source: str
    heading: str
    body: str
    kind: str
    symbols: list[str]
    score: float | None = None  # None for an exact-name match, which is not ranked


def search(question: str, k: int = 6) -> list[RetrievedChunk]:
    """Signature chunks named in the question, then the k best chunks by full-text and vector rank."""
    # Connect before embedding, so an unreachable database costs no embedding call.
    with psycopg.connect(database_url(), autocommit=True, connect_timeout=10) as conn:
        exact = exact_matches(conn, question)
        [embedding] = client.embed([question], "RETRIEVAL_QUERY")
        rows = conn.execute(SEARCH_SQL, {"question": question, "embedding": embedding, "pool": POOL, "k": k})
        ranked = [RetrievedChunk(*row[:6], score=float(row[6])) for row in rows]
    found = {chunk.id for chunk in exact}
    return exact + [chunk for chunk in ranked if chunk.id not in found]


def exact_matches(conn: psycopg.Connection, question: str) -> list[RetrievedChunk]:
    """Signature chunks for the names in the question, in order of first mention, at most MAX_EXACT_NAMES."""
    names = list(dict.fromkeys(NAME.findall(question)))
    if not names:
        return []
    chunks = [RetrievedChunk(*row) for row in conn.execute(EXACT_SQL, {"names": names})]
    chunks.sort(key=lambda chunk: (min(names.index(symbol) for symbol in chunk.symbols if symbol in names), chunk.id))
    return chunks[:MAX_EXACT_NAMES]
