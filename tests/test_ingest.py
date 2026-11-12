import json
import math
from pathlib import Path

import psycopg
import pytest

from config import EmbeddingSettings
from ingest import (
    Chunk,
    IngestCounts,
    content_hash,
    ingest,
    note_chunks,
    read_chunks,
    read_text,
    script_chunk,
    search_text,
    signature_chunks,
    text_chunk,
)
from ingest.__main__ import main
from llm import client

FIXTURES = Path(__file__).parent / "fixtures"


def stored(url: str, query: str) -> list[tuple[object, ...]]:
    with psycopg.connect(url) as conn:
        return conn.execute(query).fetchall()


def test_each_note_section_becomes_a_chunk_headed_by_title_and_section() -> None:
    chunks = note_chunks("# Test note\n\n## First\nFirst body.\n\n## Second\nSecond body.\n", "kb/notes/test.md")
    assert [(chunk.heading, chunk.body) for chunk in chunks] == [
        ("Test note: First", "First body."),
        ("Test note: Second", "Second body."),
    ]
    assert {(chunk.source, chunk.kind) for chunk in chunks} == {("kb/notes/test.md", "note")}


def test_a_heading_inside_a_code_fence_does_not_start_a_section() -> None:
    [chunk] = note_chunks("# Test note\n\n## Section\nBefore.\n```\n## not a heading\n```\nAfter.\n", "kb/notes/x.md")
    assert chunk.body == "Before.\n```\n## not a heading\n```\nAfter."


def test_text_before_the_first_section_is_reported(caplog: pytest.LogCaptureFixture) -> None:
    [chunk] = note_chunks("# Test note\n\nIntro.\n\n## Section\nBody.\n", "kb/notes/x.md")
    assert chunk.body == "Body."
    assert "kb/notes/x.md: text before the first ## section is not ingested" in caplog.text


def test_a_long_section_is_reported_but_kept_whole(caplog: pytest.LogCaptureFixture) -> None:
    [chunk] = note_chunks(f"# Test note\n\n## Long\n{'x' * 2_001}\n", "kb/notes/x.md")
    assert len(chunk.body) == 2_001
    assert "section 'Long' has 2001 characters" in caplog.text


def test_a_note_without_a_title_is_rejected() -> None:
    with pytest.raises(ValueError, match="kb/notes/x.md must start with a '# Title' line"):
        note_chunks("## Section\nBody.\n", "kb/notes/x.md")


def test_a_script_is_headed_by_its_first_comment_that_is_not_an_annotation() -> None:
    script = (FIXTURES / "E01_ok.pine").read_text(encoding="utf-8")
    text = script.replace("//@version=6\n", "//@version=6\n// Test script built from the E01_ok fixture.\n")
    chunk = script_chunk(text, "kb/scripts/entry.pine")
    assert (chunk.heading, chunk.body, chunk.kind) == ("Test script built from the E01_ok fixture.", text.strip(), "script")
    assert chunk.symbols == ["strategy.entry", "strategy.long"]


def test_a_script_without_a_description_comment_is_rejected() -> None:
    with pytest.raises(ValueError, match="kb/scripts/entry.pine needs a comment line"):
        script_chunk((FIXTURES / "E01_ok.pine").read_text(encoding="utf-8"), "kb/scripts/entry.pine")


def test_a_signature_chunk_is_the_signature_line_and_the_summary(knowledge_base: tuple[Path, Path]) -> None:
    _, signatures = knowledge_base
    rsi, _ = signature_chunks(signatures.read_text(encoding="utf-8"), "data/signatures.json")
    assert rsi == Chunk(
        "data/signatures.json",
        "ta.rsi",
        "ta.rsi(source: series int/float, length: simple int) → series float\n"
        "Relative strength index of source over length bars.",
        "signature",
        ["ta.rsi"],
    )


def test_a_signature_without_a_summary_is_rejected() -> None:
    text = json.dumps({"functions": {"ta.rsi": {"params": [], "returns": "series float"}}})
    with pytest.raises(ValueError, match="ta.rsi needs params with a name and type, returns and summary"):
        signature_chunks(text, "data/signatures.json")


def test_signature_data_without_a_functions_object_is_rejected() -> None:
    with pytest.raises(ValueError, match="data/signatures.json must be JSON with a functions object"):
        signature_chunks('{"function": {}}', "data/signatures.json")


def test_text_is_nfkc_normalised_and_zero_width_characters_are_removed(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("\ufeffｔａ.ｒｓｉ\u200b and \ufb01ll", encoding="utf-8")
    assert read_text(path) == "ta.rsi and fill"


def test_symbols_are_the_dotted_names_in_heading_and_body_sorted_once() -> None:
    chunk = text_chunk("kb/notes/x.md", "About ta.rsi", "Use color.new, then ta.rsi again. Not 3.5.", "note")
    assert chunk.symbols == ["color.new", "ta.rsi"]


def test_search_text_adds_the_symbols_with_and_without_dots() -> None:
    chunk = Chunk("kb/notes/x.md", "Heading", "Body", "note", ["color.new", "ta.rsi"])
    assert search_text(chunk) == "Heading\nBody\ncolor.new ta.rsi\ncolor new ta rsi"


def test_the_content_hash_changes_with_the_embedding_model_but_not_the_key() -> None:
    chunk = Chunk("kb/notes/x.md", "Heading", "Body", "note", [])
    digest = content_hash(chunk, EmbeddingSettings("key", "model-a", 768))
    assert digest == content_hash(chunk, EmbeddingSettings("other-key", "model-a", 768))
    assert digest != content_hash(chunk, EmbeddingSettings("key", "model-b", 768))


def test_a_missing_knowledge_base_folder_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="is not a directory"):
        read_chunks(tmp_path / "kb", tmp_path / "data" / "signatures.json")


def test_a_missing_signatures_file_is_reported(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    (tmp_path / "kb").mkdir()
    assert read_chunks(tmp_path / "kb", tmp_path / "data" / "signatures.json") == []
    assert "ingesting no signatures" in caplog.text


def test_ingest_stores_each_section_script_and_signature(
    database: str, embed_calls: list[tuple[list[str], str]], knowledge_base: tuple[Path, Path]
) -> None:
    assert ingest(*knowledge_base) == IngestCounts(added=5, removed=0, unchanged=0)
    assert stored(database, "select kind, source, heading, symbols from chunks order by id") == [
        ("note", "kb/notes/test.md", "Test note: Line colours", ["color.new"]),
        ("note", "kb/notes/test.md", "Test note: Background", []),
        ("script", "kb/scripts/entry.pine", "Test script built from the E01_ok fixture.", ["strategy.entry", "strategy.long"]),
        ("signature", "data/signatures.json", "ta.rsi", ["ta.rsi"]),
        ("signature", "data/signatures.json", "probe", ["probe"]),
    ]
    [(text,)] = stored(database, "select search_text from chunks where heading = 'ta.rsi'")
    assert text.endswith("\nta.rsi\nta rsi")


def test_documents_are_embedded_in_batches_with_the_document_task(
    database: str,
    embed_calls: list[tuple[list[str], str]],
    knowledge_base: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ingest.EMBED_BATCH_SIZE", 2)
    ingest(*knowledge_base)
    assert [len(texts) for texts, _ in embed_calls] == [2, 2, 1]
    assert {task for _, task in embed_calls} == {"RETRIEVAL_DOCUMENT"}
    assert embed_calls[0][0][0] == "Test note: Line colours\n\nThis section mentions color.new by name."


def test_a_second_ingest_without_changes_makes_no_embedding_calls(
    database: str, embed_calls: list[tuple[list[str], str]], knowledge_base: tuple[Path, Path]
) -> None:
    ingest(*knowledge_base)
    rows = stored(database, "select id, content_hash from chunks order by id")
    embed_calls.clear()
    assert ingest(*knowledge_base) == IngestCounts(added=0, removed=0, unchanged=5)
    assert embed_calls == []
    assert stored(database, "select id, content_hash from chunks order by id") == rows


def test_only_changed_chunks_are_embedded_and_removed_ones_are_deleted(
    database: str, embed_calls: list[tuple[list[str], str]], knowledge_base: tuple[Path, Path]
) -> None:
    kb, signatures = knowledge_base
    ingest(kb, signatures)
    note = kb / "notes" / "test.md"
    note.write_text(note.read_text(encoding="utf-8").replace("behind", "under"), encoding="utf-8")
    (kb / "scripts" / "entry.pine").unlink()
    embed_calls.clear()
    assert ingest(kb, signatures) == IngestCounts(added=1, removed=2, unchanged=3)
    text = "Test note: Background\n\nThis section is about shading under the bars."
    assert embed_calls == [([text], "RETRIEVAL_DOCUMENT")]
    assert stored(database, "select id, heading from chunks order by id") == [
        (1, "Test note: Line colours"),
        (4, "ta.rsi"),
        (5, "probe"),
        (6, "Test note: Background"),
    ]


def test_changing_the_embedding_model_embeds_every_chunk_again(
    database: str,
    embed_calls: list[tuple[list[str], str]],
    knowledge_base: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingest(*knowledge_base)
    monkeypatch.setenv("EMBED_MODEL", "another-embedding-model")
    assert ingest(*knowledge_base) == IngestCounts(added=5, removed=5, unchanged=0)


def test_a_failed_write_keeps_the_previous_rows(
    database: str,
    embed_calls: list[tuple[list[str], str]],
    knowledge_base: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb, signatures = knowledge_base
    ingest(kb, signatures)
    rows = stored(database, "select id, content_hash from chunks order by id")
    (kb / "scripts" / "entry.pine").unlink()
    note = kb / "notes" / "test.md"
    note.write_text(note.read_text(encoding="utf-8").replace("behind", "under"), encoding="utf-8")
    monkeypatch.setattr(client, "embed", lambda texts, task: [[math.nan] * 768 for _ in texts])
    with pytest.raises(psycopg.DataError, match="NaN not allowed in vector"):
        ingest(kb, signatures)
    assert stored(database, "select id, content_hash from chunks order by id") == rows


def test_an_unreachable_database_stops_ingest_before_any_embedding(
    embed_calls: list[tuple[list[str], str]], knowledge_base: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@db.invalid:5432/postgres")
    with pytest.raises(psycopg.OperationalError):
        ingest(*knowledge_base)
    assert embed_calls == []


def test_the_command_reports_what_it_changed(
    database: str,
    embed_calls: list[tuple[list[str], str]],
    knowledge_base: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    kb, signatures = knowledge_base
    monkeypatch.setenv("KB_DIR", str(kb))
    monkeypatch.setattr("ingest.__main__.SIGNATURES_FILE", signatures)
    assert main() == 0
    assert capsys.readouterr().out == "Chunks: 5 added, 0 removed, 0 unchanged.\n"


def test_the_command_reports_a_failure_in_one_line(
    embed_calls: list[tuple[list[str], str]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setenv("KB_DIR", str(missing))
    assert main() == 1
    assert capsys.readouterr().err == f"Ingest failed: {missing} is not a directory. Set KB_DIR to the knowledge base folder.\n"
    assert embed_calls == []
