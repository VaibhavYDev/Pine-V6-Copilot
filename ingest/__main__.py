import logging
import sys
from pathlib import Path

import psycopg

from config import kb_dir
from ingest import SIGNATURES_FILE, ingest
from llm.client import ModelCallError


def main() -> int:
    logging.basicConfig(format="%(levelname)s %(message)s")
    try:
        counts = ingest(Path(kb_dir()), SIGNATURES_FILE)
    except (RuntimeError, ValueError, ModelCallError, psycopg.Error) as error:
        print(f"Ingest failed: {error}", file=sys.stderr)
        return 1
    print(f"Chunks: {counts.added} added, {counts.removed} removed, {counts.unchanged} unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
