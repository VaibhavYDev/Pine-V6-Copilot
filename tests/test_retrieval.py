from pathlib import Path

import psycopg
import pytest

from ingest import ingest
from retrieval import search

# A chunk ranked by only one of the two searches scores at most 1/61; one ranked by both (pool 20) at least 2/80.
SINGLE_LIST_LIMIT = 1 / 60


@pytest.fixture
def ingested(database: str, embed_calls: list[tuple[list[str], str]], knowledge_base: tuple[Path, Path]) -> None:
    ingest(*knowledge_base)
    embed_calls.clear()


def test_a_dotted_name_returns_its_signature_first(ingested: None) -> None:
    first = search("How do I call ta.rsi on closing prices?")[0]
    assert (first.heading, first.kind, first.score) == ("ta.rsi", "signature", None)


def test_a_bare_function_name_returns_its_signature_first(ingested: None) -> None:
    first = search("When is probe the right call?")[0]
    assert (first.heading, first.kind, first.score) == ("probe", "signature", None)


def test_exact_matches_follow_the_order_of_mention(ingested: None) -> None:
    chunks = search("Compare probe with ta.rsi")
    assert [chunk.heading for chunk in chunks if chunk.score is None] == ["probe", "ta.rsi"]


def test_exact_matches_stop_at_the_name_limit(ingested: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("retrieval.MAX_EXACT_NAMES", 1)
    chunks = search("Compare ta.rsi with probe")
    assert [chunk.heading for chunk in chunks if chunk.score is None] == ["ta.rsi"]


def test_a_word_inside_a_dotted_name_is_found_by_text_search(ingested: None) -> None:
    chunks = search("what does rsi do")
    assert all(chunk.score is not None for chunk in chunks)
    assert chunks[0].heading == "ta.rsi"
    assert chunks[0].score > SINGLE_LIST_LIMIT


def test_a_question_of_stopwords_still_returns_vector_ranked_chunks(ingested: None) -> None:
    chunks = search("what is the")
    assert len(chunks) == 5
    assert all(chunk.score is not None and chunk.score < SINGLE_LIST_LIMIT for chunk in chunks)


def test_an_exact_match_is_not_repeated_among_the_ranked_chunks(ingested: None) -> None:
    ids = [chunk.id for chunk in search("ta.rsi")]
    assert len(ids) == 5
    assert len(set(ids)) == len(ids)


def test_ranked_chunks_come_in_score_order_up_to_k(ingested: None) -> None:
    chunks = search("line colours and background shading", k=3)
    scores = [chunk.score for chunk in chunks]
    assert len(scores) == 3
    assert scores == sorted(scores, reverse=True)
    assert chunks[0].heading in ("Test note: Line colours", "Test note: Background")


def test_the_question_is_embedded_once_with_the_query_task(
    ingested: None, embed_calls: list[tuple[list[str], str]]
) -> None:
    search("line colours")
    assert embed_calls == [(["line colours"], "RETRIEVAL_QUERY")]


def test_a_hostile_question_is_searched_as_plain_text(ingested: None, database: str) -> None:
    search("x'); drop table chunks; -- \\' \" | & ! :* ( ) <-> ta.rsi'")
    with psycopg.connect(database) as conn:
        assert conn.execute("select count(*) from chunks").fetchone() == (5,)


def test_an_empty_table_returns_no_chunks(database: str, embed_calls: list[tuple[list[str], str]]) -> None:
    assert search("How do I call ta.rsi on closing prices?") == []


def test_an_unreachable_database_fails_before_the_question_is_embedded(
    embed_calls: list[tuple[list[str], str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@db.invalid:5432/postgres")
    with pytest.raises(psycopg.OperationalError):
        search("line colours")
    assert embed_calls == []
