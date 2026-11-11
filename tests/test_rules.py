import re
from pathlib import Path

import pytest

from checker import Finding, check

FIXTURES = Path(__file__).parent / "fixtures"
RULES_DOC = (Path(__file__).parents[1] / "docs" / "rules.md").read_text(encoding="utf-8")
IMPLEMENTED = {"E01", "E02", "E13"}


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.pine").read_text(encoding="utf-8")


def documented(rule: str) -> tuple[str, str, int]:
    """Severity, message template and expected line from the rule's section in docs/rules.md."""
    section = re.search(rf"^## {rule} .*?(?=^## |\Z)", RULES_DOC, re.M | re.S).group()
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


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*_ok.pine")), ids=lambda path: path.stem)
def test_ok_fixture_gives_no_finding_from_these_rules_and_no_error(path: Path) -> None:
    findings = check(path.read_text(encoding="utf-8"))
    assert [f for f in findings if f.rule in IMPLEMENTED] == []
    assert [f for f in findings if f.severity == "error"] == []


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.pine")), ids=lambda path: path.stem)
def test_fixture_findings_are_identical_on_every_run(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    assert check(source) == check(source)
