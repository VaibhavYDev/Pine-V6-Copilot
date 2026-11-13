import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from checker import Finding, check
from config import writer_model
from llm import client
from retrieval import RetrievedChunk, search

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
SYSTEM_PROMPT = (PROMPTS / "system_v1.txt").read_text(encoding="utf-8").rstrip("\n")
REPAIR_PROMPT = (PROMPTS / "repair_v1.txt").read_text(encoding="utf-8").rstrip("\n")
# repair_v1.txt keeps the blueprint's placeholder line; the error findings replace it.
FINDINGS_LINE = '{one line per error: "line 6, col 35 [E01]: <message>"}'
# BLUEPRINT 11.1 gives this template no file of its own.
USER_MESSAGE = """<UNTRUSTED_RETRIEVED_CONTENT>
{reference}
</UNTRUSTED_RETRIEVED_CONTENT>

<UNTRUSTED_USER_INPUT>
{user_input}
</UNTRUSTED_USER_INPUT>"""
NO_REFERENCE = "(no reference for this request)"
UNTRUSTED_TAG = re.compile(r"</?UNTRUSTED_(?:RETRIEVED_CONTENT|USER_INPUT)>", re.IGNORECASE)

# BLUEPRINT 11.3.
APP_TEMPERATURE = 0.2
APP_TIMEOUT = 30.0
EVAL_TEMPERATURE = 0.0
EVAL_TIMEOUT = 60.0
MAX_TOKENS = 1_500
MAX_REPAIRS = 2
# BLUEPRINT 10.3.
REFERENCE_CHARS = 6_000
# Only "stop" confirms a complete reply. Any other finish reason, or none, means no script is taken from it.
UNFINISHED_REPLIES = {"length": "truncated", "content_filter": "filtered"}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelCall:
    """One logical chat() call. The client may send its request twice; `attempts` says how often."""

    purpose: str  # "draft", "repair 1" or "repair 2"
    status: str  # "code", "no_code", "empty", "truncated", "filtered", "unconfirmed", "unclosed_fence" or "failed"
    text: str  # the raw reply, kept for evaluation; empty when the call failed
    finish_reason: str | None
    model: str | None  # as the provider reported it
    attempts: int | None  # None when the call failed
    input_tokens: int | None  # None when unknown, never a guessed 0
    output_tokens: int | None
    latency_ms: int
    error: str | None = None  # the sanitized ModelCallError message


@dataclass(frozen=True)
class Draft:
    """The first reply and the check of its script. Repairs run on this exact draft (BLUEPRINT 13.3)."""

    model: str  # CHAT_MODEL; the repairs use the same model
    user_message: str
    sources: list[str]
    retrieved_ids: list[int]
    call: ModelCall
    code: str | None
    findings: list[Finding]
    created_at: str
    retrieval_ms: int
    latency_ms: int


@dataclass(frozen=True)
class Answer:
    draft: Draft
    code: str | None
    findings: list[Finding]
    repairs: int  # repair calls made, failed ones included
    fixed: list[str]  # error rules the draft had and `code` does not
    static_check_status: str  # "no_code", "passed", "warnings", "errors" or "parse_failed"; never a compile result
    stop_reason: str  # "no_code", "repair_off", "no_errors", "repair_limit" or "repair_failed"
    calls: list[ModelCall]
    input_tokens: int  # successful calls only
    output_tokens: int
    prompt_version: str  # the prompt files actually sent
    latency_ms: int


@dataclass(frozen=True)
class Candidate:
    code: str
    findings: list[Finding]
    reply: str


def answer(
    question: str,
    code: str | None = None,
    retrieve: bool = True,
    repair: bool = True,
    *,
    temperature: float = APP_TEMPERATURE,
    timeout: float = APP_TIMEOUT,
) -> Answer:
    """BLUEPRINT 11.2: draft, check, then repair error findings at most twice."""
    draft = write_draft(question, code, retrieve, temperature=temperature, timeout=timeout)
    return answer_from_draft(draft, repair, temperature=temperature, timeout=timeout)


def write_draft(
    question: str,
    code: str | None = None,
    retrieve: bool = True,
    *,
    temperature: float = APP_TEMPERATURE,
    timeout: float = APP_TIMEOUT,
) -> Draft:
    """Look up references when asked, request the first reply and check its script.

    A failed draft call raises ModelCallError, since there is no candidate to fall back on.
    """
    started = time.perf_counter()
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    model = writer_model()
    reference, used = build_reference(search(question) if retrieve else [])
    retrieval_ms = elapsed_ms(started)
    message = user_message(reference, question, code)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message}]
    call, script = send("draft", messages, model, temperature, timeout)
    if call.status == "failed":
        raise client.ModelCallError(call.error)
    return Draft(
        model=model,
        user_message=message,
        sources=[chunk.heading for chunk in used],
        retrieved_ids=[chunk.id for chunk in used],
        call=call,
        code=script,
        findings=check(script) if script is not None else [],
        created_at=created_at,
        retrieval_ms=retrieval_ms,
        latency_ms=elapsed_ms(started),
    )


def answer_from_draft(
    draft: Draft, repair: bool = True, *, temperature: float = APP_TEMPERATURE, timeout: float = APP_TIMEOUT
) -> Answer:
    """Check and repair a saved draft without writing a new one, so A0/A2 and A1/A3 share their drafts."""
    started = time.perf_counter()
    if draft.code is None:
        candidates, repair_calls, stop_reason = [], [], "no_code"
    elif not repair:
        candidates, repair_calls = [Candidate(draft.code, draft.findings, draft.call.text)], []
        stop_reason = "repair_off"
    else:
        candidates, repair_calls, stop_reason = run_repairs(draft, temperature, timeout)
    # Fewest errors wins, the earlier on a tie. A script the parser could not read never beats one it could,
    # because its zero errors only mean that no rule ran.
    best = min(candidates, key=lambda c: (parse_failed(c.findings), len(errors(c.findings))), default=None)
    code, findings = (best.code, best.findings) if best else (None, [])
    calls = [draft.call, *repair_calls]
    result = Answer(
        draft=draft,
        code=code,
        findings=findings,
        repairs=len(repair_calls),
        fixed=sorted({f.rule for f in errors(draft.findings)} - {f.rule for f in errors(findings)}),
        static_check_status=static_check_status(code, findings),
        stop_reason=stop_reason,
        calls=calls,
        input_tokens=sum(call.input_tokens for call in calls if call.input_tokens is not None),
        output_tokens=sum(call.output_tokens for call in calls if call.output_tokens is not None),
        prompt_version="system_v1+repair_v1" if repair_calls else "system_v1",
        latency_ms=draft.latency_ms + elapsed_ms(started),
    )
    logger.info(
        "answer draft=%s stop=%s repairs=%d input_tokens=%d output_tokens=%d duration_ms=%d",
        draft.call.status, stop_reason, result.repairs, result.input_tokens, result.output_tokens, result.latency_ms,
    )
    return result


def run_repairs(draft: Draft, temperature: float, timeout: float) -> tuple[list[Candidate], list[ModelCall], str]:
    """BLUEPRINT 11.2 step 5: repair the latest script while it has errors, at most MAX_REPAIRS times."""
    current = Candidate(draft.code, draft.findings, draft.call.text)
    candidates: list[Candidate] = [current]
    calls: list[ModelCall] = []
    while errors(current.findings):
        if len(calls) == MAX_REPAIRS:
            return candidates, calls, "repair_limit"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": draft.user_message},
            {"role": "assistant", "content": current.reply},
            {"role": "user", "content": repair_prompt(current.findings)},
        ]
        call, script = send(f"repair {len(calls) + 1}", messages, draft.model, temperature, timeout)
        calls.append(call)
        if call.status == "failed":
            return candidates, calls, "repair_failed"
        # A reply without a usable script still used up an attempt; the previous script stays current.
        if script is not None:
            current = Candidate(script, check(script), call.text)
            candidates.append(current)
    return candidates, calls, "no_errors"


def send(
    purpose: str, messages: list[dict[str, str]], model: str, temperature: float, timeout: float
) -> tuple[ModelCall, str | None]:
    """One logical chat() call, and the script its reply holds when the reply is confirmed complete."""
    started = time.perf_counter()
    try:
        reply = client.chat(messages, model, MAX_TOKENS, temperature, timeout)
    except client.ModelCallError as error:
        failed = ModelCall(
            purpose=purpose,
            status="failed",
            text="",
            finish_reason=None,
            model=None,
            attempts=None,
            input_tokens=None,
            output_tokens=None,
            latency_ms=elapsed_ms(started),
            error=str(error),
        )
        return failed, None
    status, script = read_reply(reply.text, reply.finish_reason)
    call = ModelCall(
        purpose=purpose,
        status=status,
        text=reply.text,
        finish_reason=reply.finish_reason,
        model=reply.model,
        attempts=reply.attempts,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
        latency_ms=elapsed_ms(started),
    )
    return call, script


def read_reply(text: str, finish_reason: str | None) -> tuple[str, str | None]:
    """What a reply holds, and its script. A cut-off, filtered or unconfirmed reply never gives a script."""
    if finish_reason != "stop":
        return UNFINISHED_REPLIES.get(finish_reason, "unconfirmed"), None
    if not text.strip():
        return "empty", None
    if fenced_blocks(text)[1]:
        return "unclosed_fence", None
    script = extract_pine(text)
    if script is None or not script.strip():
        return "no_code", None
    return "code", script


def extract_pine(reply: str) -> str | None:
    """BLUEPRINT 11.2, except that a fence left open gives no script: the reply may have been cut short."""
    blocks, unclosed = fenced_blocks(reply)
    if unclosed:
        return None
    for block in blocks:
        if "//@version" in block:
            return block
    if blocks:
        return blocks[0]
    if reply.lstrip().startswith("//@version"):
        return reply.strip()
    return None


def fenced_blocks(reply: str) -> tuple[list[str], bool]:
    """The contents of each complete ``` block, and whether the last fence was left open."""
    blocks: list[str] = []
    current: list[str] | None = None
    for line in reply.splitlines():
        if line.lstrip().startswith("```"):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
        elif current is not None:
            current.append(line)
    return blocks, current is not None


def build_reference(chunks: list[RetrievedChunk]) -> tuple[str, list[RetrievedChunk]]:
    """BLUEPRINT 10.3: signatures, then notes and scripts in rank order, within REFERENCE_CHARS.

    A chunk that does not fit is skipped whole and later ones are still tried; no chunk is shortened.
    """
    ordered = [chunk for chunk in chunks if chunk.kind == "signature"]
    ordered += [chunk for chunk in chunks if chunk.kind != "signature"]
    used: list[RetrievedChunk] = []
    for chunk in ordered:
        if len(reference_text([*used, chunk])) <= REFERENCE_CHARS:
            used.append(chunk)
    return reference_text(used), used


def reference_text(chunks: list[RetrievedChunk]) -> str:
    """One line per signature, then each note or script as its heading and body."""
    lines = [chunk.body.split("\n", 1)[0] for chunk in chunks if chunk.kind == "signature"]
    blocks = [f"{chunk.heading}\n{chunk.body}" for chunk in chunks if chunk.kind != "signature"]
    return "\n\n".join(part for part in ["\n".join(lines), *blocks] if part)


def user_message(reference: str, question: str, code: str | None) -> str:
    """BLUEPRINT 11.1. No content keeps a copy of the block tags, so none can close its own block."""
    user_input = f"{question}\n{code}" if code else question
    return USER_MESSAGE.format(reference=strip_tags(reference) or NO_REFERENCE, user_input=strip_tags(user_input))


def strip_tags(text: str) -> str:
    """Removes the block tags in any letter case, repeatedly, since removing one can join the pieces of another."""
    while UNTRUSTED_TAG.search(text):
        text = UNTRUSTED_TAG.sub("", text)
    return text


def repair_prompt(findings: list[Finding]) -> str:
    """repair_v1.txt with one line per error finding. Warnings are never sent."""
    lines = [f"line {f.line}, col {f.col} [{f.rule}]: {f.message}" for f in errors(findings)]
    return REPAIR_PROMPT.replace(FINDINGS_LINE, "\n".join(lines))


def errors(findings: list[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.severity == "error"]


def parse_failed(findings: list[Finding]) -> bool:
    return any(finding.rule == "E00" for finding in findings)


def static_check_status(code: str | None, findings: list[Finding]) -> str:
    """What the static checker found. It says nothing about whether the Pine Editor compiles the script."""
    if code is None:
        return "no_code"
    if parse_failed(findings):
        return "parse_failed"
    if errors(findings):
        return "errors"
    return "warnings" if findings else "passed"


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
