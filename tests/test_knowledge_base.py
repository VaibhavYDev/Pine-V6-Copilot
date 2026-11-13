import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from ingest import SIGNATURES_FILE, read_chunks

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "kb"
SCRIPT_RECORDS = ROOT / "review" / "script_verification.csv"


def script_records() -> list[dict[str, str]]:
    with SCRIPT_RECORDS.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def without_repeated_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"repeated keys: {sorted({key for key in keys if keys.count(key) > 1})}")
    return dict(pairs)


def test_every_script_has_exactly_one_verification_record() -> None:
    recorded = Counter(record["filename"] for record in script_records())
    assert recorded == Counter(path.name for path in (KB / "scripts").glob("*.pine"))


def test_each_recorded_hash_matches_the_script_bytes() -> None:
    # A Pine Editor result applies only to the exact bytes it was recorded for (BLUEPRINT 8.1 and 8.5).
    changed = [
        record["filename"]
        for record in script_records()
        if hashlib.sha256((KB / "scripts" / record["filename"]).read_bytes()).hexdigest() != record["sha256"]
    ]
    assert changed == []


def test_signatures_have_the_documented_shape() -> None:
    signatures = json.loads(SIGNATURES_FILE.read_text(encoding="utf-8"), object_pairs_hook=without_repeated_keys)
    assert set(signatures) == {"complete_namespaces", "functions"}
    assert all(isinstance(namespace, str) for namespace in signatures["complete_namespaces"])
    for name, entry in signatures["functions"].items():
        assert set(entry) == {"params", "returns", "params_complete", "summary"}, name
        assert isinstance(entry["params_complete"], bool), name
        assert all(set(param) == {"name", "type"} and param["name"] and param["type"] for param in entry["params"]), name
        param_names = [param["name"] for param in entry["params"]]
        assert len(param_names) == len(set(param_names)), name
        assert entry["returns"] and entry["summary"], name


def test_the_knowledge_base_reads_as_ingest_reads_it() -> None:
    chunks = read_chunks(KB, SIGNATURES_FILE)
    assert {chunk.kind for chunk in chunks} == {"note", "script", "signature"}
