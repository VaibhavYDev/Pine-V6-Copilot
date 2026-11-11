import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from pynescript import ast as pine

MAX_CHARS = 40_000
MAX_LINES = 800
MAX_NESTING = 50
# The pattern pynescript's comment parser uses for a version annotation.
VERSION_COMMENT = re.compile(r"//\s*@\s*version\s*=\s*(.+)")


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

    # pynescript keeps only the annotations written before the first statement, but a version comment
    # may appear anywhere, so version annotations come from a scan of the source instead.
    annotations = [note for note in tree.annotations if not VERSION_COMMENT.fullmatch(note)]
    tree.annotations = annotations + version_comments(source)
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


def version_comments(source: str) -> list[str]:
    """Every //@version comment, skipping string literals the way the pynescript lexer does."""
    ends = {quote: string_ends(source, quote) for quote in "\"'"}
    comments = []
    i = 0
    while i < len(source):
        char = source[i]
        if char in ends and ends[char][i + 1] is not None:
            i = ends[char][i + 1] + 1
        elif source.startswith("//", i):
            end = source.find("\n", i)
            end = len(source) if end == -1 else end
            if VERSION_COMMENT.fullmatch(source, i, end):
                comments.append(source[i:end])
            i = end
        else:
            i += 1
    return comments


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
DECLARATIONS = {"indicator", "strategy", "library"}
STRATEGY_ONLY_CALLS = {"strategy.entry"}
LEGACY_REPLACEMENTS = {
    "study": "`indicator()`",
    "security": "`request.security()`",
    "iff": "the `?:` operator",
    "tostring": "`str.tostring()`",
    "tonumber": "`str.tonumber()`",
}


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


def duplicate_named_args(tree: pine.AST) -> Iterator[Finding]:
    for node in pine.walk(tree):
        if not isinstance(node, pine.Call):
            continue
        seen = set()
        for arg in node.args:
            if arg.name in seen:
                function = call_name(node)
                target = f"{function}()" if function else "this call"
                message = f"`{arg.name}` is passed more than once to {target}. Keep one."
                yield Finding("E07", "warning", arg.lineno, arg.col_offset, message)
            if arg.name:
                seen.add(arg.name)


def legacy_calls(tree: pine.AST) -> Iterator[tuple[str, pine.Call]]:
    """Calls to built-ins that Pine v6 no longer has, skipping functions the script defines itself."""
    defined = {node.name for node in pine.walk(tree) if isinstance(node, pine.FunctionDef)}
    for node in pine.walk(tree):
        function = call_name(node) if isinstance(node, pine.Call) else None
        if function in LEGACY_REPLACEMENTS and function not in defined:
            yield function, node


def removed_builtins(tree: pine.AST) -> Iterator[Finding]:
    for function, node in legacy_calls(tree):
        message = f"{function}() is not available in Pine v6. Use {LEGACY_REPLACEMENTS[function]} instead."
        yield Finding("E11", "warning", node.lineno, node.col_offset, message)


def not_v6_version(tree: pine.AST) -> Iterator[Finding]:
    matches = (VERSION_COMMENT.fullmatch(note) for note in tree.annotations)
    versions = [match.group(1).strip() for match in matches if match]
    if not versions:
        message = (
            "Add `//@version=6`: this project targets Pine v6. "
            "This is a compliance warning, not a confirmed compile error."
        )
        yield Finding("E14", "warning", 1, 0, message)
    for version in versions:
        if version != "6":
            message = (
                f"`//@version={version}` is not Pine v6. Use `//@version=6`; "
                "this is a compliance warning, not a confirmed compile error."
            )
            yield Finding("E14", "warning", 1, 0, message)


def invalid_declarations(tree: pine.AST) -> Iterator[Finding]:
    declarations = [
        node for node in pine.walk(tree) if isinstance(node, pine.Call) and call_name(node) in DECLARATIONS
    ]
    top_level = [
        statement.value
        for statement in tree.body
        if isinstance(statement, pine.Expr)
        and isinstance(statement.value, pine.Call)
        and call_name(statement.value) in DECLARATIONS
    ]
    if not top_level:
        # A study() call gets an E11 finding, which already explains the missing declaration.
        if not any(function == "study" for function, _ in legacy_calls(tree)):
            message = (
                "No top-level indicator(), strategy() or library() declaration. "
                "Add exactly one at the top level."
            )
            yield Finding("E15", "warning", 1, 0, message)
        return
    for node in declarations:
        if node is not top_level[0]:
            message = "Only one indicator(), strategy() or library() declaration is allowed. Remove this one."
            yield Finding("E15", "warning", node.lineno, node.col_offset, message)
    if call_name(top_level[0]) == "indicator":
        for node in pine.walk(tree):
            function = call_name(node) if isinstance(node, pine.Call) else None
            if function in STRATEGY_ONLY_CALLS:
                message = f"{function}() requires a strategy() declaration, but this script is an indicator()."
                yield Finding("E15", "warning", node.lineno, node.col_offset, message)


# A rule is added only with its owner-approved docs/rules.md section and fixtures (BLUEPRINT 9.7).
RULES: list[Callable[[pine.AST], Iterable[Finding]]] = [
    removed_when_param,
    removed_transp_param,
    plot_in_local_block,
    duplicate_named_args,
    removed_builtins,
    not_v6_version,
    invalid_declarations,
]
