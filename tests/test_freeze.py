from pathlib import Path

from eval.freeze import check_lock, hash_tasks, write_lock


def freeze_two_tasks(tmp_path: Path) -> tuple[Path, Path]:
    golden = tmp_path / "golden"
    golden.mkdir()
    (golden / "a.toml").write_bytes(b'id = "a"\n')
    (golden / "b.toml").write_bytes(b'id = "b"\n')
    lock = tmp_path / "golden.lock"
    write_lock(golden, lock)
    return golden, lock


def test_matching_lock_passes(tmp_path: Path) -> None:
    golden, lock = freeze_two_tasks(tmp_path)
    assert check_lock(golden, lock) == []


def test_changed_task_fails(tmp_path: Path) -> None:
    golden, lock = freeze_two_tasks(tmp_path)
    (golden / "a.toml").write_bytes(b'id = "edited"\n')
    assert check_lock(golden, lock) == ["changed: a.toml"]


def test_added_task_fails(tmp_path: Path) -> None:
    golden, lock = freeze_two_tasks(tmp_path)
    (golden / "c.toml").write_bytes(b'id = "c"\n')
    assert check_lock(golden, lock) == ["added: c.toml"]


def test_removed_task_fails(tmp_path: Path) -> None:
    golden, lock = freeze_two_tasks(tmp_path)
    (golden / "b.toml").unlink()
    assert check_lock(golden, lock) == ["missing: b.toml"]


def test_missing_lock_fails_even_without_tasks(tmp_path: Path) -> None:
    problems = check_lock(tmp_path / "golden", tmp_path / "golden.lock")
    assert len(problems) == 1
    assert "golden.lock is missing" in problems[0]


def test_empty_lock_without_tasks_passes(tmp_path: Path) -> None:
    lock = tmp_path / "golden.lock"
    write_lock(tmp_path / "golden", lock)
    assert lock.read_bytes() == b""
    assert check_lock(tmp_path / "golden", lock) == []


def test_crlf_and_lf_tasks_hash_the_same(tmp_path: Path) -> None:
    (tmp_path / "lf").mkdir()
    (tmp_path / "crlf").mkdir()
    (tmp_path / "lf" / "a.toml").write_bytes(b'id = "a"\nquestion = "q"\n')
    (tmp_path / "crlf" / "a.toml").write_bytes(b'id = "a"\r\nquestion = "q"\r\n')
    assert hash_tasks(tmp_path / "lf") == hash_tasks(tmp_path / "crlf")


def test_lock_checked_out_with_crlf_still_matches(tmp_path: Path) -> None:
    golden, lock = freeze_two_tasks(tmp_path)
    lock.write_bytes(lock.read_bytes().replace(b"\n", b"\r\n"))
    assert check_lock(golden, lock) == []


def test_files_other_than_toml_are_ignored(tmp_path: Path) -> None:
    golden, lock = freeze_two_tasks(tmp_path)
    (golden / "desktop.ini").write_bytes(b"[.ShellClassInfo]\n")
    assert check_lock(golden, lock) == []
