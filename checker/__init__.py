from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from pynescript import ast as pine

MAX_CHARS = 40_000
MAX_LINES = 800
MAX_NESTING = 50


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str  # "error" or "warning"
    line: int
    col: int
    message: str


def check(source: str) -> list[Finding]:
    """Raise ValueError when the source is over the size or nesting limits."""
    source = prepare_source(source)
    try:
        tree = pine.parse(source)
    except pine.SyntaxError as err:
        where = err.details
        return [parser_failure(where.lineno, where.offset, err.message)]
    except RecursionError:
        return [parser_failure(1, 0, "the code is nested too deeply")]
    except ValueError as err:
        # pynescript raises this for a literal it cannot convert; it is not an input-limit rejection.
        return [parser_failure(1, 0, str(err))]

    findings = [finding for rule in RULES for finding in rule(tree)]
    return sorted(findings, key=lambda f: (f.line, f.col, f.rule))


def parser_failure(line: int, col: int, reason: str) -> Finding:
    # E00 stays a warning: a pynescript failure is not proof that the Pine compiler rejects the code (BLUEPRINT 9.3).
    message = f"pynescript could not parse this code: {reason}. Official compiler failure is unverified."
    return Finding("E00", "warning", line, col, message)


def prepare_source(source: str) -> str:
    """Normalise line endings and blank Markdown fence lines; raise ValueError when a limit is exceeded."""
    if len(source) > MAX_CHARS:
        raise ValueError(f"Code has {len(source):,} characters; the limit is {MAX_CHARS:,}.")
    text = source.replace("\r\n", "\n").replace("\r", "\n")
    line_count = len(text.splitlines())
    if line_count > MAX_LINES:
        raise ValueError(f"Code has {line_count} lines; the limit is {MAX_LINES}.")

    # Fence lines are blanked, not removed, so finding line numbers match the pasted text.
    lines = text.split("\n")
    filled = [i for i, line in enumerate(lines) if line.strip()]
    if filled and lines[filled[0]].lstrip().startswith("```"):
        lines[filled[0]] = ""
    if len(filled) > 1 and lines[filled[-1]].strip() == "```":
        lines[filled[-1]] = ""
    text = "\n".join(lines)

    depth = deepest_nesting(text)
    if depth > MAX_NESTING:
        raise ValueError(f"Brackets are nested {depth} levels deep; the limit is {MAX_NESTING}.")
    return text


def deepest_nesting(source: str) -> int:
    """Deepest ( and [ nesting outside string literals and // comments, read the way the pynescript lexer reads them."""
    ends = {quote: string_ends(source, quote) for quote in "\"'"}
    depth = deepest = 0
    i = 0
    while i < len(source):
        char = source[i]
        if char in ends and ends[char][i + 1] is not None:
            i = ends[char][i + 1] + 1
            continue
        if source.startswith("//", i):
            newline = source.find("\n", i)
            if newline == -1:
                break
            i = newline
        elif char in "([":
            depth += 1
            deepest = max(deepest, depth)
        elif char in ")]":
            depth = max(depth - 1, 0)
        i += 1
    return deepest


def string_ends(source: str, quote: str) -> list[int | None]:
    """ends[i] is the index of the quote closing a string whose content starts at i, or None if it never closes.

    As in the lexer, a backslash escapes the next character, strings may span lines, and a quote that never
    closes is a lone token, so the brackets after it still count.
    """
    ends: list[int | None] = [None] * (len(source) + 2)
    for i in range(len(source) - 1, -1, -1):
        if source[i] == quote:
            ends[i] = i
        elif source[i] == "\\":
            ends[i] = ends[i + 2]
        else:
            ends[i] = ends[i + 1]
    return ends


def call_name(call: pine.Call) -> str | None:
    """'ta.sma' for ta.sma(...), 'plot' for plot(...), None when the callee isn't a plain name."""
    parts = []
    node = call.func
    while isinstance(node, pine.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, pine.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


# Coverage and severities follow docs/rules.md: each rule covers only the case its fixtures show and
# stays a warning until the owner records Pine Editor results.
WHEN_CALLS = {"strategy.entry"}
TRANSP_CALLS = {"plot"}
GLOBAL_ONLY_CALLS = {"plot"}
LOCAL_BLOCKS = (pine.If,)


def named_args(tree: pine.AST, functions: set[str], name: str) -> Iterator[tuple[str, pine.Arg]]:
    for node in pine.walk(tree):
        function = call_name(node) if isinstance(node, pine.Call) else None
        if function in functions:
            for arg in node.args:
                if arg.name == name:
                    yield function, arg


def removed_when_param(tree: pine.AST) -> Iterator[Finding]:
    for function, arg in named_args(tree, WHEN_CALLS, "when"):
        message = f"`when` is not supported by {function}() in Pine v6. Guard the call with `if`."
        yield Finding("E01", "warning", arg.lineno, arg.col_offset, message)


def removed_transp_param(tree: pine.AST) -> Iterator[Finding]:
    for function, arg in named_args(tree, TRANSP_CALLS, "transp"):
        message = f"`transp` is not supported by {function}() in Pine v6. Use `color.new()` when appropriate."
        yield Finding("E02", "warning", arg.lineno, arg.col_offset, message)


def plot_in_local_block(tree: pine.AST) -> Iterator[Finding]:
    def visit(node: pine.AST, inside_block: bool) -> Iterator[Finding]:
        function = call_name(node) if isinstance(node, pine.Call) else None
        if inside_block and function in GLOBAL_ONLY_CALLS:
            message = (
                f"{function}() cannot be called in a local scope. "
                "Move it to global scope and make its series or color conditional."
            )
            yield Finding("E13", "warning", node.lineno, node.col_offset, message)
        inside_block = inside_block or isinstance(node, LOCAL_BLOCKS)
        for child in pine.iter_child_nodes(node):
            yield from visit(child, inside_block)

    yield from visit(tree, False)


# A rule is added only with its owner-approved docs/rules.md section and fixtures (BLUEPRINT 9.7).
RULES: list[Callable[[pine.AST], Iterable[Finding]]] = [
    removed_when_param,
    removed_transp_param,
    plot_in_local_block,
]
