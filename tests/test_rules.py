import re
from pathlib import Path

import pytest

from checker import Finding, check

FIXTURES = Path(__file__).parent / "fixtures"
RULES_DOC = (Path(__file__).parents[1] / "docs" / "rules.md").read_text(encoding="utf-8")
IMPLEMENTED = {"E01", "E02", "E07", "E11", "E13", "E14", "E15"}


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.pine").read_text(encoding="utf-8")


def rule_section(rule: str) -> str:
    return re.search(rf"^## {rule} .*?(?=^## |\Z)", RULES_DOC, re.M | re.S).group()


def documented_severity(rule: str) -> str:
    return re.search(r"^- \*\*Severity:\*\* (\w+)", rule_section(rule), re.M).group(1)


def message_templates(rule: str) -> dict[str, str]:
    """Message templates from the rule's section, keyed by case ("" when the rule has one message)."""
    return dict(re.findall(r"^- \*\*Message \(template\)(?:, ([^:*]+))?:\*\* (.+)$", rule_section(rule), re.M))


def documented_position(name: str) -> tuple[int, int]:
    """Line and column that docs/rules.md records for a bad fixture."""
    found = re.search(rf"`tests/fixtures/{name}\.pine`.*?line \*\*(\d+)\*\*, column \*\*(\d+)\*\*", RULES_DOC)
    return int(found[1]), int(found[2])


def documented(rule: str) -> tuple[str, str, int]:
    """Severity, message template and expected line from the rule's section in docs/rules.md."""
    section = rule_section(rule)
    severity = re.search(r"^- \*\*Severity:\*\* (\w+)", section, re.M).group(1)
    template = re.search(r"^- \*\*Message \(template\):\*\* (.+)$", section, re.M).group(1)
    line = re.search(r"expected finding line \*\*(\d+)\*\*", section).group(1)
    return severity, template, int(line)


@pytest.mark.parametrize(
    ("rule", "function", "line", "col"),
    [("E01", "strategy.entry", 4, 38), ("E02", "plot", 3, 30), ("E13", "plot", 4, 4)],
)
def test_bad_fixture_gives_exactly_the_documented_finding(rule: str, function: str, line: int, col: int) -> None:
    severity, template, documented_line = documented(rule)
    findings = [f for f in check(fixture(f"{rule}_bad")) if f.rule in IMPLEMENTED]
    assert documented_line == line
    assert findings == [Finding(rule, severity, line, col, template.format(function=function))]


BAD_FIXTURES = [
    ("E07_bad", "E07", 3, 25, "", {"argument": "title", "call": "plot()"}),
    ("E11_bad", "E11", 3, 12, "", {"function": "tostring", "replacement": "`str.tostring()`"}),
    ("E11_bad_tonumber", "E11", 3, 8, "", {"function": "tonumber", "replacement": "`str.tonumber()`"}),
    ("E11_bad_iff", "E11", 3, 9, "", {"function": "iff", "replacement": "the `?:` operator"}),
    ("E11_bad_security", "E11", 3, 13, "", {"function": "security", "replacement": "`request.security()`"}),
    ("E11_bad_study", "E11", 2, 0, "", {"function": "study", "replacement": "`indicator()`"}),
    ("E14_bad", "E14", 1, 0, "missing", {}),
    ("E14_bad_v5", "E14", 1, 0, "other version", {"version": "5"}),
    ("E14_bad_string", "E14", 1, 0, "missing", {}),
    ("E15_bad", "E15", 1, 0, "missing", {}),
    ("E15_bad_local", "E15", 1, 0, "missing", {}),
    ("E15_bad_two", "E15", 3, 0, "duplicate", {}),
    ("E15_bad_order", "E15", 4, 4, "strategy call in indicator", {"function": "strategy.entry"}),
]


@pytest.mark.parametrize(
    ("name", "rule", "line", "col", "case", "values"), BAD_FIXTURES, ids=[case[0] for case in BAD_FIXTURES]
)
def test_each_bad_fixture_gives_exactly_its_documented_finding(
    name: str, rule: str, line: int, col: int, case: str, values: dict[str, str]
) -> None:
    message = message_templates(rule)[case].format(**values)
    findings = [f for f in check(fixture(name)) if f.rule in IMPLEMENTED]
    assert documented_position(name) == (line, col)
    assert findings == [Finding(rule, documented_severity(rule), line, col, message)]


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*_ok*.pine")), ids=lambda path: path.stem)
def test_ok_fixture_gives_no_finding_from_these_rules_and_no_error(path: Path) -> None:
    findings = check(path.read_text(encoding="utf-8"))
    assert [f for f in findings if f.rule in IMPLEMENTED] == []
    assert [f for f in findings if f.severity == "error"] == []


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.pine")), ids=lambda path: path.stem)
def test_fixture_findings_are_identical_on_every_run(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    assert check(source) == check(source)
