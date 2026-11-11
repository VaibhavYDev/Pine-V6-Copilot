import argparse
import hashlib
import sys
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / "golden"
LOCK_FILE = Path(__file__).parent / "golden.lock"


def hash_tasks(golden_dir: Path) -> dict[str, str]:
    hashes = {}
    for path in golden_dir.rglob("*.toml"):
        # Git on Windows can check the tasks out with CRLF, so hash them with LF endings.
        content = path.read_bytes().replace(b"\r\n", b"\n")
        hashes[path.relative_to(golden_dir).as_posix()] = hashlib.sha256(content).hexdigest()
    return hashes


def read_lock(lock_file: Path) -> dict[str, str]:
    hashes = {}
    for line in lock_file.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        hashes[name] = digest
    return hashes


def write_lock(golden_dir: Path, lock_file: Path) -> int:
    hashes = hash_tasks(golden_dir)
    lines = [f"{hashes[name]}  {name}\n" for name in sorted(hashes)]
    lock_file.write_text("".join(lines), encoding="utf-8", newline="\n")
    return len(lines)


def check_lock(golden_dir: Path, lock_file: Path) -> list[str]:
    """Return one line per difference between the task files and the lock; empty when they match."""
    if not lock_file.exists():
        return [f"{lock_file.name} is missing. The owner creates it with: python -m eval.freeze"]
    locked = read_lock(lock_file)
    current = hash_tasks(golden_dir)
    problems = [f"missing: {name}" for name in sorted(locked.keys() - current.keys())]
    problems += [f"added: {name}" for name in sorted(current.keys() - locked.keys())]
    problems += [
        f"changed: {name}"
        for name in sorted(locked.keys() & current.keys())
        if locked[name] != current[name]
    ]
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write eval/golden.lock (owner only) or, with --check, compare the task files with it."
    )
    parser.add_argument("--check", action="store_true", help="exit 1 if the task files differ from the lock")
    args = parser.parse_args()
    if not args.check:
        count = write_lock(GOLDEN_DIR, LOCK_FILE)
        print(f"Wrote {count} task hashes to eval/golden.lock.")
        return 0
    problems = check_lock(GOLDEN_DIR, LOCK_FILE)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("Task files match eval/golden.lock.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
