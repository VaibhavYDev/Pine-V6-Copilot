import inspect
import logging
import re
import subprocess
import sys
from dataclasses import asdict, fields
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import NOTE, app, check_code
from checker import MAX_CHARS, MAX_LINES, MAX_NESTING, check
from config import Settings

FIXTURES = Path(__file__).parent / "fixtures"
STATIC = Path(__file__).parents[1] / "api" / "static"
POLICY = "default-src 'self'"
client = TestClient(app)


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.pine").read_text(encoding="utf-8")


def test_valid_request_returns_findings_counts_and_note() -> None:
    response = client.post("/check", json={"code": fixture("E01_ok")})
    assert response.status_code == 200
    assert response.json() == {"findings": [], "errors": 0, "warnings": 0, "note": NOTE}


@pytest.mark.parametrize(
    ("name", "rule", "line", "col"),
    [
        ("E01_bad", "E01", 4, 38),
        ("E02_bad", "E02", 3, 30),
        ("E13_bad", "E13", 4, 4),
        ("E07_bad", "E07", 3, 25),
        ("E11_bad", "E11", 3, 12),
        ("E14_bad", "E14", 1, 0),
        ("E15_bad", "E15", 1, 0),
    ],
)
def test_each_rule_is_reported_from_its_fixture(name: str, rule: str, line: int, col: int) -> None:
    body = client.post("/check", json={"code": fixture(name)}).json()
    [finding] = body["findings"]
    assert (finding["rule"], finding["line"], finding["col"]) == (rule, line, col)
    assert set(finding) == {"rule", "severity", "line", "col", "message"}


def test_counts_follow_finding_severities() -> None:
    # A fragment from docs/rules.md (W01): it has neither a version annotation nor a declaration.
    body = client.post("/check", json={"code": "ratio = 5 / 2"}).json()
    assert {"E14", "E15"} <= {finding["rule"] for finding in body["findings"]}
    assert body["errors"] == sum(finding["severity"] == "error" for finding in body["findings"])
    assert body["warnings"] == sum(finding["severity"] == "warning" for finding in body["findings"])


@pytest.mark.parametrize("code", ["", "   ", "\n\t \n"])
def test_empty_or_blank_code_is_rejected(code: str) -> None:
    response = client.post("/check", json={"code": code})
    assert response.status_code == 422
    assert response.json() == {"detail": "Paste some Pine Script code to check."}


@pytest.mark.parametrize(
    ("code", "limit"),
    [
        ("x" * (MAX_CHARS + 1), "40,000"),
        ("x\n" * (MAX_LINES + 1), "800"),
        ("(" * (MAX_NESTING + 1) + ")" * (MAX_NESTING + 1), "50"),
    ],
    ids=["characters", "lines", "nesting"],
)
def test_code_over_a_limit_is_rejected_without_echoing_it(code: str, limit: str) -> None:
    response = client.post("/check", json={"code": code})
    assert response.status_code == 422
    assert limit in response.json()["detail"]
    assert len(response.text) < 200


@pytest.mark.parametrize("payload", [{}, {"code": 5}, {"source": "x"}])
def test_malformed_request_gets_a_plain_422(payload: dict[str, object]) -> None:
    response = client.post("/check", json=payload)
    assert response.status_code == 422
    assert response.json() == {"detail": 'Send a JSON body with a "code" string.'}


def test_invalid_json_gets_a_plain_422() -> None:
    response = client.post("/check", content=b"{not json", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {"detail": 'Send a JSON body with a "code" string.'}


def test_parser_failure_is_a_200_with_an_e00_warning() -> None:
    response = client.post("/check", json={"code": "This is not Pine code."})
    assert response.status_code == 200
    [finding] = response.json()["findings"]
    assert (finding["rule"], finding["severity"]) == ("E00", "warning")
    assert "unverified" in finding["message"]


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.pine")), ids=lambda path: path.stem)
def test_endpoint_returns_exactly_what_the_checker_finds(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    findings = check(source)
    body = client.post("/check", json={"code": source}).json()
    assert body["findings"] == [asdict(finding) for finding in findings]
    assert body["errors"] == sum(finding.severity == "error" for finding in findings)
    assert body["warnings"] == sum(finding.severity == "warning" for finding in findings)


def test_check_endpoint_runs_in_a_worker_thread() -> None:
    assert not inspect.iscoroutinefunction(check_code)


def test_check_logs_timing_and_count_but_not_the_code(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="api.app")
    client.post("/check", json={"code": fixture("E01_bad")})
    assert "findings=1" in caplog.text
    assert "strategy.entry" not in caplog.text


def test_check_works_without_model_database_or_env_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for item in fields(Settings):
        monkeypatch.delenv(item.name.upper(), raising=False)
    response = client.post("/check", json={"code": fixture("E01_bad")})
    assert response.status_code == 200
    assert response.json()["warnings"] == 1


def test_api_imports_no_config_model_or_database_code() -> None:
    probe = (
        "import sys, api.app; "
        "print([m for m in ('config', 'llm', 'psycopg', 'openai', 'google.genai') if m in sys.modules])"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "[]"


@pytest.mark.parametrize(
    ("path", "content_type"),
    [("/", "text/html"), ("/static/app.js", "javascript"), ("/static/style.css", "text/css")],
)
def test_page_and_assets_are_served_under_the_security_policy(path: str, content_type: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert response.headers["content-security-policy"] == POLICY


def test_check_responses_carry_the_security_policy() -> None:
    assert client.post("/check", json={"code": "x"}).headers["content-security-policy"] == POLICY
    assert client.post("/check", json={"code": ""}).headers["content-security-policy"] == POLICY


def test_docs_pages_that_need_a_cdn_are_disabled() -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_frontend_writes_text_safely_and_loads_nothing_external() -> None:
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    styles = (STATIC / "style.css").read_text(encoding="utf-8")
    for unsafe in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert unsafe not in script
    assert "textContent" in script
    for text in (script, page, styles):
        assert "http://" not in text
        assert "https://" not in text
    scripts = re.findall(r"<script([^>]*)>(.*?)</script>", page, re.S)
    assert scripts
    assert all("src=" in attributes and not body.strip() for attributes, body in scripts)
    assert "<style" not in page
    assert " style=" not in page
