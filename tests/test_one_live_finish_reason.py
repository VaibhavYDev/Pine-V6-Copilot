import importlib.util
import os
import socket
from pathlib import Path
from types import ModuleType

import pytest

from llm.client import ModelCallError, Reply
from pipeline.answer import APP_TIMEOUT, MAX_TOKENS

HELPER = Path(__file__).resolve().parents[1] / "review" / "one_live_finish_reason.py"
AUTHORIZED = ["--authorize-one-live-call"]
TYPED_KEY = "typed-writer-key"
REPLY_TEXT = "READY, plus reply text that must stay private"
STOPPED = Reply(REPLY_TEXT, 14, 3, "writer-model-2026", 210, "stop", 1)


def load_helper() -> ModuleType:
    """The helper loaded from its file: review/ is not an installed package."""
    spec = importlib.util.spec_from_file_location("one_live_finish_reason", HELPER)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


@pytest.fixture(autouse=True)
def blocked_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError("network access is disabled in tests")

    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture(autouse=True)
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAT_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("CHAT_MODEL", "writer-model")
    monkeypatch.delenv("CHAT_API_KEY", raising=False)
    monkeypatch.delenv("JUDGE_MODEL", raising=False)


def run_probe(
    monkeypatch: pytest.MonkeyPatch, outcome: Reply | Exception, typed_key: str = TYPED_KEY
) -> tuple[int, list[dict[str, object]]]:
    """Run the authorized helper against a fake chat() that records each call, then returns or raises `outcome`."""
    helper = load_helper()
    calls: list[dict[str, object]] = []

    def fake_chat(
        messages: list[dict[str, str]], model: str, max_tokens: int, temperature: float, timeout: float = 30.0
    ) -> Reply:
        key = os.environ.get("CHAT_API_KEY")
        calls.append({"model": model, "max_tokens": max_tokens, "timeout": timeout, "key": key})
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(helper, "chat", fake_chat)
    monkeypatch.setattr(helper, "getpass", lambda prompt: typed_key)
    return helper.main(AUTHORIZED), calls


def test_loading_the_helper_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llm.client.chat", lambda *args, **kwargs: pytest.fail("chat() ran on import"))
    monkeypatch.setattr("getpass.getpass", lambda *args, **kwargs: pytest.fail("the key was requested on import"))
    load_helper()


def test_nothing_is_sent_without_the_authorization_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    helper = load_helper()
    monkeypatch.setattr(helper, "chat", lambda *args, **kwargs: pytest.fail("chat() was called"))
    monkeypatch.setattr(helper, "getpass", lambda *args, **kwargs: pytest.fail("the key was requested"))
    with pytest.raises(SystemExit) as stopped:
        helper.main([])
    assert stopped.value.code == 2


def test_one_request_uses_the_pipeline_limits_and_prints_metadata_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    status, calls = run_probe(monkeypatch, STOPPED)
    printed = capsys.readouterr().out
    assert status == 0
    assert calls == [{"model": "writer-model", "max_tokens": MAX_TOKENS, "timeout": APP_TIMEOUT, "key": TYPED_KEY}]
    assert "finish_reason: 'stop'" in printed and "provider_requests: 1" in printed
    for private in (REPLY_TEXT, TYPED_KEY, "Reply with exactly"):
        assert private not in printed
    assert "CHAT_API_KEY" not in os.environ


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", None])
def test_a_reply_that_did_not_stop_fails_the_probe(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], finish_reason: str | None
) -> None:
    status, calls = run_probe(monkeypatch, Reply(REPLY_TEXT, 14, MAX_TOKENS, "writer-model-2026", 900, finish_reason, 2))
    printed = capsys.readouterr().out
    assert (status, len(calls)) == (1, 1)
    assert f"finish_reason: {finish_reason!r}" in printed and "provider_requests: 2" in printed
    assert REPLY_TEXT not in printed


def test_a_failed_call_prints_only_the_sanitized_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = ModelCallError("Writer model writer-model failed: HTTP 401, authentication failed; check CHAT_API_KEY")
    status, calls = run_probe(monkeypatch, error)
    printed = capsys.readouterr().out
    assert (status, len(calls)) == (1, 1)
    assert "HTTP 401" in printed and TYPED_KEY not in printed
    assert "CHAT_API_KEY" not in os.environ


@pytest.mark.parametrize(
    ("setting", "value", "typed_key"),
    [
        ("CHAT_MODEL", "", TYPED_KEY),
        ("CHAT_BASE_URL", "https://api.openai.com/v1", TYPED_KEY),
        ("CHAT_API_KEY", "", ""),
    ],
    ids=["no model", "unapproved host", "no key typed"],
)
def test_config_rejects_incomplete_settings_before_any_request(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], setting: str, value: str, typed_key: str
) -> None:
    monkeypatch.setenv(setting, value)
    status, calls = run_probe(monkeypatch, STOPPED, typed_key)
    assert (status, calls) == (1, [])
    assert setting in capsys.readouterr().out
    assert "CHAT_API_KEY" not in os.environ
