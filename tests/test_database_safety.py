import re
import uuid

import psycopg
import pytest
from conftest import TEST_DATABASE_PREFIX, temporary_database
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo


def database_exists(admin_url: str, name: str) -> bool:
    with psycopg.connect(admin_url) as conn:
        return conn.execute("select exists (select from pg_database where datname = %s)", [name]).fetchone() == (True,)


def test_the_session_database_is_new_and_not_the_one_database_url_names(admin_url: str, test_database_url: str) -> None:
    name = conninfo_to_dict(test_database_url)["dbname"]
    assert re.fullmatch(f"{TEST_DATABASE_PREFIX}[0-9a-f]{{32}}", name)
    assert name != conninfo_to_dict(admin_url).get("dbname")
    assert database_exists(admin_url, name)


def test_each_temporary_database_has_its_own_name_and_is_dropped_on_exit(admin_url: str) -> None:
    with temporary_database(admin_url, "select 1") as first, temporary_database(admin_url, "select 1") as second:
        names = [conninfo_to_dict(url)["dbname"] for url in (first, second)]
        assert names[0] != names[1]
        assert all(database_exists(admin_url, name) for name in names)
    assert not any(database_exists(admin_url, name) for name in names)


def test_a_failing_schema_still_drops_the_new_database(admin_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    new = uuid.uuid4()
    monkeypatch.setattr(uuid, "uuid4", lambda: new)
    with pytest.raises(psycopg.errors.SyntaxError), temporary_database(admin_url, "this is not sql"):
        pass
    assert not database_exists(admin_url, TEST_DATABASE_PREFIX + new.hex)


def test_a_failing_test_still_drops_the_new_database(admin_url: str) -> None:
    with pytest.raises(AssertionError), temporary_database(admin_url, "select 1") as url:
        name = conninfo_to_dict(url)["dbname"]
        raise AssertionError("a failing test")
    assert not database_exists(admin_url, name)


def test_an_existing_database_is_never_dropped_even_when_database_url_names_it(
    admin_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    taken = uuid.uuid4()
    name = TEST_DATABASE_PREFIX + taken.hex
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    existing_url = make_conninfo(admin_url, dbname=name)
    try:
        with psycopg.connect(existing_url, autocommit=True) as conn:
            conn.execute("create table kept (id int)")
        monkeypatch.setattr(uuid, "uuid4", lambda: taken)
        with pytest.raises(psycopg.errors.DuplicateDatabase), temporary_database(existing_url, "select 1"):
            pass
        with psycopg.connect(existing_url) as conn:
            assert conn.execute("select to_regclass('kept') is not null").fetchone() == (True,)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(sql.SQL("drop database {} with (force)").format(sql.Identifier(name)))
