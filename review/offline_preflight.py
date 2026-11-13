"""Read-only preflight for a local Pine v6 Copilot repository. No API or DB calls."""
from collections import Counter
from pathlib import Path

from checker import check
from ingest import read_chunks


def main() -> None:
    kb = Path("kb")
    sig = Path("data/signatures.json")
    chunks = read_chunks(kb, sig)
    print("Knowledge-base chunks:", dict(Counter(item.kind for item in chunks)))
    scripts = sorted((kb / "scripts").glob("*.pine"))
    for path in scripts:
        findings = check(path.read_text(encoding="utf-8"))
        summary = ", ".join(f"{finding.rule}:{finding.severity}" for finding in findings) or "none"
        print(f"{path.as_posix()}: offline findings = {summary}")
    print("No Pine Editor/compiler verification performed. No network, embeddings or database accessed.")


if __name__ == "__main__":
    main()
