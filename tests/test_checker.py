import dataclasses
import subprocess
import sys

import pytest
from pynescript import ast as pine

import checker
from checker import (
    MAX_CHARS,
    MAX_LINES,
    MAX_NESTING,
    Finding,
    call_name,
    check,
    deepest_nesting,
    prepare_source,
    version_comments,
)

PROSE = "This is not Pine code."


@pytest.fixture
def no_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checker, "RULES", [])


@pytest.fixture
def stub_parser(monkeypatch: pytest.MonkeyPatch, no_rules: None) -> None:
    monkeypatch.setattr(pine, "parse", lambda source: pine.Script(body=[], annotations=[]))


def raise_from_parser(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def parse(source: str) -> pine.AST:
        raise error

    monkeypatch.setattr(pine, "parse", parse)


def test_finding_is_immutable() -> None:
    finding = Finding("E00", "warning", 1, 0, "message")
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.line = 2


def test_finding_fields_match_the_report_contract() -> None:
    finding = Finding("E00", "warning", 1, 0, "message")
    assert dataclasses.asdict(finding) == {"rule": "E00", "severity": "warning", "line": 1, "col": 0, "message": "message"}


def test_findings_are_sorted_by_line_column_and_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    first = [Finding("R2", "warning", 3, 0, ""), Finding("R2", "warning", 1, 4, "")]
    second = [Finding("R1", "warning", 1, 4, ""), Finding("R3", "warning", 1, 0, "")]
    monkeypatch.setattr(checker, "RULES", [lambda tree: first, lambda tree: second])
    assert [(f.line, f.col, f.rule) for f in check("")] == [(1, 0, "R3"), (1, 4, "R1"), (1, 4, "R2"), (3, 0, "R2")]


def test_identical_input_gives_identical_findings() -> None:
    assert check(PROSE) == check(PROSE)


def test_empty_input_parses_without_findings(no_rules: None) -> None:
    assert check("") == []
    assert check("\n\n") == []


def test_parser_failure_is_an_e00_warning_at_the_parser_position() -> None:
    [finding] = check("\n\n)")
    assert (finding.rule, finding.severity, finding.line, finding.col) == ("E00", "warning", 3, 0)


def test_parser_failure_message_names_the_parser_and_leaves_the_compiler_unverified() -> None:
    [finding] = check(PROSE)
    assert (finding.line, finding.col) == (1, 8)
    assert "pynescript" in finding.message
    assert "unverified" in finding.message


def test_parser_recursion_error_becomes_an_e00_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    raise_from_parser(monkeypatch, RecursionError())
    [finding] = check("x")
    assert (finding.rule, finding.severity, finding.line, finding.col) == ("E00", "warning", 1, 0)


def test_parser_value_error_becomes_an_e00_warning_not_a_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    raise_from_parser(monkeypatch, ValueError("Invalid float literal: 1e"))
    [finding] = check("x")
    assert finding.rule == "E00"
    assert "Invalid float literal: 1e" in finding.message


def test_input_at_the_character_limit_is_accepted(stub_parser: None) -> None:
    assert check("x" * MAX_CHARS) == []


def test_input_over_the_character_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="40,000"):
        check("x" * (MAX_CHARS + 1))


def test_input_at_the_line_limit_is_accepted(stub_parser: None) -> None:
    assert check("x\n" * MAX_LINES) == []


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_input_over_the_line_limit_is_rejected(newline: str) -> None:
    with pytest.raises(ValueError, match="800"):
        check(f"x{newline}" * (MAX_LINES + 1))


def test_nesting_at_the_limit_is_accepted(stub_parser: None) -> None:
    assert check("(" * MAX_NESTING + ")" * MAX_NESTING) == []


def test_nesting_over_the_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="nested 51 levels"):
        check("[" + "(" * MAX_NESTING + ")" * MAX_NESTING + "]")


@pytest.mark.parametrize(
    ("source", "depth"),
    [
        ("([" * 3 + "])" * 3, 6),
        ('"' + "(" * 60 + '"', 0),
        ("'" + "(" * 60 + "'", 0),
        ('"\\"' + "(" * 60 + '"', 0),
        ("// " + "(" * 60, 0),
        ('"' + "(" * 60, 60),
        ('"//"' + "(" * 60, 60),
    ],
)
def test_nesting_ignores_strings_and_comments_but_not_an_unclosed_quote(source: str, depth: int) -> None:
    assert deepest_nesting(source) == depth


@pytest.mark.parametrize(
    ("source", "comments"),
    [
        ("//@version=6\nx = 1", ["//@version=6"]),
        ("x = 1\n// @version = 6", ["// @version = 6"]),
        ('note = "//@version=6"', []),
        ("note = '//@version=5'\n//@version=6", ["//@version=6"]),
        ("// a plain comment", []),
    ],
)
def test_version_comments_are_found_anywhere_except_inside_strings(source: str, comments: list[str]) -> None:
    assert version_comments(source) == comments


def test_line_endings_become_lf() -> None:
    assert prepare_source("a\r\nb\rc\n") == "a\nb\nc\n"


def test_fence_lines_are_blanked_to_keep_line_numbers() -> None:
    assert prepare_source("```pine\nbody\n```\n") == "\nbody\n\n"
    assert prepare_source("a\n```\nb") == "a\n```\nb"


def test_parser_position_in_fenced_crlf_input_matches_the_pasted_text() -> None:
    [finding] = check("```pine\r\n\r\n)\r\n```")
    assert (finding.line, finding.col) == (3, 0)


def test_call_name_joins_a_plain_name_or_attribute_chain() -> None:
    chain = pine.Attribute(value=pine.Attribute(value=pine.Name(id="a"), attr="b"), attr="c")
    assert call_name(pine.Call(func=pine.Name(id="f"), args=[])) == "f"
    assert call_name(pine.Call(func=chain, args=[])) == "a.b.c"


def test_call_name_is_none_when_the_callee_is_not_a_name() -> None:
    subscript = pine.Subscript(value=pine.Name(id="f"), slice=pine.Constant(value=1))
    assert call_name(pine.Call(func=subscript, args=[])) is None
    assert call_name(pine.Call(func=pine.Call(func=pine.Name(id="f"), args=[]), args=[])) is None


def test_checker_imports_no_config_model_or_database_code() -> None:
    probe = "import sys, checker; print([m for m in ('config', 'llm', 'psycopg', 'openai', 'google.genai') if m in sys.modules])"
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "[]"
