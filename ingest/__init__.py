import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass
from itertools import batched
from pathlib import Path

import psycopg

from config import EmbeddingSettings, database_url, embedding_settings
from llm import client

SIGNATURES_FILE = Path(__file__).resolve().parents[1] / "data" / "signatures.json"
MAX_SECTION_CHARS = 2_000
# Texts per embedding request. The installed SDK documents no limit, so this stays modest.
EMBED_BATCH_SIZE = 50
ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
DOTTED_NAME = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")

INSERT_CHUNK = """
insert into chunks (source, heading, body, kind, symbols, search_text, embedding, content_hash)
values (%(source)s, %(heading)s, %(body)s, %(kind)s, %(symbols)s, %(search_text)s, %(embedding)s::vector,
        %(content_hash)s)
on conflict (content_hash) do nothing
"""
DELETE_CHUNKS = "delete from chunks where content_hash = any(%(hashes)s)"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Chunk:
    source: str
    heading: str
    body: str
    kind: str
    symbols: list[str]


@dataclass(frozen=True)
class IngestCounts:
    added: int
    removed: int
    unchanged: int


def ingest(kb: Path, signatures: Path) -> IngestCounts:
    """Make the chunks table match the knowledge base, embedding only chunks it does not hold yet."""
    settings = embedding_settings()
    chunks = {content_hash(chunk, settings): chunk for chunk in read_chunks(kb, signatures)}
    with psycopg.connect(database_url(), autocommit=True, connect_timeout=10) as conn:
        stored = {digest for (digest,) in conn.execute("select content_hash from chunks")}
        new = {digest: chunk for digest, chunk in chunks.items() if digest not in stored}
        gone = sorted(stored - chunks.keys())
        vectors = embed_chunks(list(new.values()))
        rows = [
            asdict(chunk) | {"search_text": search_text(chunk), "embedding": vector, "content_hash": digest}
            for (digest, chunk), vector in zip(new.items(), vectors, strict=True)
        ]
        # One transaction, so a failed insert leaves the previous rows in place.
        with conn.transaction():
            if gone:
                conn.execute(DELETE_CHUNKS, {"hashes": gone})
            with conn.cursor() as cursor:
                cursor.executemany(INSERT_CHUNK, rows)
    return IngestCounts(added=len(new), removed=len(gone), unchanged=len(chunks) - len(new))


def embed_chunks(chunks: list[Chunk]) -> list[list[float]]:
    vectors = []
    for batch in batched(chunks, EMBED_BATCH_SIZE):
        vectors += client.embed([f"{chunk.heading}\n\n{chunk.body}" for chunk in batch], "RETRIEVAL_DOCUMENT")
    return vectors


def read_chunks(kb: Path, signatures: Path) -> list[Chunk]:
    if not kb.is_dir():
        raise ValueError(f"{kb} is not a directory. Set KB_DIR to the knowledge base folder.")
    chunks = []
    for path in sorted(kb.glob("notes/*.md")):
        chunks += note_chunks(read_text(path), source_name(path, kb))
    for path in sorted(kb.glob("scripts/*.pine")):
        chunks.append(script_chunk(read_text(path), source_name(path, kb)))
    if signatures.is_file():
        chunks += signature_chunks(read_text(signatures), source_name(signatures, signatures.parent))
    else:
        logger.warning("%s not found; ingesting no signatures.", signatures)
    return chunks


def read_text(path: Path) -> str:
    return ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", path.read_text(encoding="utf-8")))


def source_name(path: Path, folder: Path) -> str:
    """The path from `folder`'s parent, such as kb/notes/arrays.md, whatever the working directory."""
    return path.resolve().relative_to(folder.resolve().parent).as_posix()


def note_chunks(text: str, source: str) -> list[Chunk]:
    """One chunk per ## section. A ## line inside a code fence does not start a section."""
    lines = text.strip().splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"{source} must start with a '# Title' line.")
    title = lines[0][2:].strip()
    intro: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    in_fence = False
    for line in lines[1:]:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
        else:
            intro.append(line)
    if any(line.strip() for line in intro):
        logger.warning("%s: text before the first ## section is not ingested.", source)
    chunks = []
    for section, section_lines in sections:
        body = "\n".join(section_lines).strip()
        if len(body) > MAX_SECTION_CHARS:
            logger.warning(
                "%s: section %r has %d characters; keep a section under %d.", source, section, len(body),
                MAX_SECTION_CHARS,
            )
        chunks.append(text_chunk(source, f"{title}: {section}", body, "note"))
    return chunks


def script_chunk(text: str, source: str) -> Chunk:
    """The whole script, headed by its first comment line that is not a //@ annotation."""
    for line in text.splitlines():
        comment = line.strip()
        heading = comment.lstrip("/").strip()
        if comment.startswith("//") and not comment.startswith("//@") and heading:
            return text_chunk(source, heading, text.strip(), "script")
    raise ValueError(f"{source} needs a comment line that says what the script does.")


def signature_chunks(text: str, source: str) -> list[Chunk]:
    try:
        functions = json.loads(text)["functions"]
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"{source} must be JSON with a functions object ({error!r}).") from None
    chunks = []
    for name, function in functions.items():
        try:
            params = ", ".join(f"{param['name']}: {param['type']}" for param in function["params"])
            body = f"{name}({params}) → {function['returns']}\n{function['summary']}"
        except (KeyError, TypeError):
            raise ValueError(f"{source}: {name} needs params with a name and type, returns and summary.") from None
        chunks.append(Chunk(source, name, body, "signature", [name]))
    return chunks


def text_chunk(source: str, heading: str, body: str, kind: str) -> Chunk:
    symbols = sorted(set(DOTTED_NAME.findall(f"{heading}\n{body}")))
    return Chunk(source, heading, body, kind, symbols)


def search_text(chunk: Chunk) -> str:
    """BLUEPRINT 10.4: the spaced copy (ta sma) lets a search for "sma" find ta.sma."""
    spaced = [symbol.replace(".", " ") for symbol in chunk.symbols]
    return "\n".join([chunk.heading, chunk.body, " ".join(chunk.symbols), " ".join(spaced)])


def content_hash(chunk: Chunk, settings: EmbeddingSettings) -> str:
    """Covers the embedding model and size too, so changing either re-embeds every chunk."""
    fields = [settings.model, settings.dim, chunk.kind, chunk.source, chunk.heading, chunk.body]
    return hashlib.sha256(json.dumps(fields).encode("utf-8")).hexdigest()
