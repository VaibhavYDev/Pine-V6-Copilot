import logging
import math
import socket
import time
from types import SimpleNamespace

import httpx2
import openai
import pytest
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from openai.types.chat import ChatCompletion

from llm.client import (
    GEMINI_EMBED_URL,
    RETRY_DELAY_SECONDS,
    ModelCallError,
    Reply,
    chat,
    embed,
)

GROQ_URL = "https://api.groq.com/openai/v1"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
WRITER_KEY = "writer-secret-key"
JUDGE_KEY = "judge-secret-key"
GEMINI_KEY = "gemini-secret-key"
PROMPT = "private prompt text"
MESSAGES = [{"role": "user", "content": PROMPT}]
TEXTS = ["private document text", "second document"]


@pytest.fixture(autouse=True)
def blocked_network(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Records and refuses every attempt to open a real connection, so no test can reach a provider."""
    attempts: list[object] = []

    def refuse(*args: object, **kwargs: object) -> None:
        attempts.append(args)
        raise OSError("network access is disabled in tests")

    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    return attempts


@pytest.fixture(autouse=True)
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = {
        "CHAT_BASE_URL": GROQ_URL,
        "CHAT_API_KEY": WRITER_KEY,
        "CHAT_MODEL": "writer-model",
        "JUDGE_BASE_URL": GEMINI_URL,
        "JUDGE_API_KEY": JUDGE_KEY,
        "JUDGE_MODEL": "judge-model",
        "GEMINI_API_KEY": GEMINI_KEY,
        "EMBED_MODEL": "gemini-embedding-001",
        "EMBED_DIM": "768",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)


class FakeOpenAI:
    """Stands in for openai.OpenAI: records its options and requests, and replays scripted outcomes."""

    def __init__(self, outcomes: list[object], **options: object) -> None:
        self.outcomes = outcomes
        self.options = options
        self.requests: list[dict[str, object]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def __enter__(self) -> "FakeOpenAI":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def create(self, **request: object) -> object:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Replaces openai.OpenAI with FakeOpenAI; each test appends the provider's replies to `outcomes`."""
    state = SimpleNamespace(outcomes=[], clients=[], sleeps=[])

    def factory(**options: object) -> FakeOpenAI:
        client = FakeOpenAI(state.outcomes, **options)
        state.clients.append(client)
        return client

    monkeypatch.setattr(openai, "OpenAI", factory)
    monkeypatch.setattr(time, "sleep", state.sleeps.append)
    return state


def completion(model: str = "writer-model", usage: bool = True) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "test",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Done."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15} if usage else None,
        }
    )


def provider_error(cls: type[openai.APIStatusError], status: int, message: str = "provider message") -> Exception:
    request = httpx2.Request("POST", GROQ_URL)
    return cls(message, response=httpx2.Response(status, request=request), body=None)


def timed_out() -> Exception:
    return openai.APITimeoutError(request=httpx2.Request("POST", GROQ_URL))


def test_writer_request_goes_to_groq_with_the_requested_settings(provider: SimpleNamespace) -> None:
    provider.outcomes.append(completion("writer-model"))
    reply = chat(MESSAGES, "writer-model", 1500, 0.2)
    assert reply == Reply("Done.", 12, 3, "writer-model", reply.latency_ms)
    [client] = provider.clients
    assert client.options == {"base_url": GROQ_URL, "api_key": WRITER_KEY, "timeout": 30.0, "max_retries": 0}
    assert client.requests == [{"model": "writer-model", "messages": MESSAGES, "max_tokens": 1500, "temperature": 0.2}]


def test_judge_request_goes_to_gemini_with_its_own_key_and_timeout(provider: SimpleNamespace) -> None:
    provider.outcomes.append(completion("judge-model"))
    reply = chat(MESSAGES, "judge-model", 1500, 0, timeout=60)
    [client] = provider.clients
    assert reply.model == "judge-model"
    assert client.options == {"base_url": GEMINI_URL, "api_key": JUDGE_KEY, "timeout": 60, "max_retries": 0}


def test_an_unconfigured_model_fails_before_any_request(provider: SimpleNamespace) -> None:
    with pytest.raises(RuntimeError, match="matches neither"):
        chat(MESSAGES, "other-model", 10, 0)
    assert provider.clients == []


def test_missing_credentials_fail_before_any_request(provider: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHAT_API_KEY")
    with pytest.raises(RuntimeError, match="CHAT_API_KEY"):
        chat(MESSAGES, "writer-model", 10, 0)
    assert provider.clients == []


def test_an_unapproved_provider_fails_before_any_request(
    provider: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHAT_BASE_URL", "https://api.openai.com/v1")
    with pytest.raises(RuntimeError, match="must be an https URL"):
        chat(MESSAGES, "writer-model", 10, 0)
    assert provider.clients == []


@pytest.mark.parametrize(
    "error",
    [
        provider_error(openai.RateLimitError, 429),
        provider_error(openai.InternalServerError, 500),
        provider_error(openai.InternalServerError, 503),
        timed_out(),
    ],
    ids=["429", "500", "503", "timeout"],
)
def test_a_transient_failure_is_retried_once(provider: SimpleNamespace, error: Exception) -> None:
    provider.outcomes.extend([error, completion()])
    assert chat(MESSAGES, "writer-model", 10, 0).text == "Done."
    assert len(provider.clients[0].requests) == 2
    assert provider.sleeps == [RETRY_DELAY_SECONDS]


@pytest.mark.parametrize(
    ("error", "hint"),
    [
        (provider_error(openai.AuthenticationError, 401), "check CHAT_API_KEY"),
        (provider_error(openai.PermissionDeniedError, 403), "check CHAT_API_KEY"),
        (provider_error(openai.BadRequestError, 400), "request rejected"),
        (provider_error(openai.NotFoundError, 404), "check CHAT_MODEL"),
        (provider_error(openai.UnprocessableEntityError, 422), "request rejected"),
    ],
    ids=["401", "403", "400", "404", "422"],
)
def test_a_permanent_failure_is_not_retried(provider: SimpleNamespace, error: Exception, hint: str) -> None:
    provider.outcomes.append(error)
    with pytest.raises(ModelCallError, match=hint):
        chat(MESSAGES, "writer-model", 10, 0)
    assert len(provider.clients[0].requests) == 1
    assert provider.sleeps == []


def test_a_second_transient_failure_ends_the_call(provider: SimpleNamespace) -> None:
    provider.outcomes.extend([timed_out(), timed_out()])
    with pytest.raises(ModelCallError, match="Writer model writer-model failed: timed out after 30 s"):
        chat(MESSAGES, "writer-model", 10, 0)
    assert len(provider.clients[0].requests) == 2
    assert provider.sleeps == [RETRY_DELAY_SECONDS]


def test_errors_and_logs_never_contain_the_key_or_the_prompt(
    provider: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    leaky = f"Incorrect API key provided: {WRITER_KEY} while handling {PROMPT}"
    provider.outcomes.extend(
        [provider_error(openai.RateLimitError, 429, leaky), provider_error(openai.AuthenticationError, 401, leaky)]
    )
    caplog.set_level(logging.WARNING, logger="llm.client")
    with pytest.raises(ModelCallError) as error:
        chat(MESSAGES, "writer-model", 10, 0)
    assert "retrying once" in caplog.text
    for secret in (WRITER_KEY, PROMPT):
        assert secret not in str(error.value)
        assert secret not in caplog.text
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__


def test_a_reply_without_token_usage_is_an_error(provider: SimpleNamespace) -> None:
    provider.outcomes.append(completion(usage=False))
    with pytest.raises(ModelCallError, match="no token usage"):
        chat(MESSAGES, "writer-model", 10, 0)


def test_the_real_client_cannot_reach_the_network_in_tests(blocked_network: list[object]) -> None:
    with pytest.raises(ModelCallError, match="could not reach CHAT_BASE_URL"):
        chat(MESSAGES, "writer-model", 10, 0)
    assert len(blocked_network) == 1


class FakeGenai:
    """Stands in for genai.Client: records its options and requests, and replays scripted outcomes."""

    def __init__(self, outcomes: list[object], **options: object) -> None:
        self.outcomes = outcomes
        self.options = options
        self.requests: list[dict[str, object]] = []
        self.models = SimpleNamespace(embed_content=self.embed_content)

    def __enter__(self) -> "FakeGenai":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def embed_content(self, **request: object) -> object:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def gemini(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Replaces genai.Client with FakeGenai; each test appends the provider's replies to `outcomes`."""
    state = SimpleNamespace(outcomes=[], clients=[], sleeps=[])

    def factory(**options: object) -> FakeGenai:
        client = FakeGenai(state.outcomes, **options)
        state.clients.append(client)
        return client

    monkeypatch.setattr(genai, "Client", factory)
    monkeypatch.setattr(time, "sleep", state.sleeps.append)
    return state


def embeddings(count: int = 2, size: int = 768) -> genai_types.EmbedContentResponse:
    return vectors([[0.5] * size for _ in range(count)])


def vectors(values: list[list[float] | None]) -> genai_types.EmbedContentResponse:
    return genai_types.EmbedContentResponse(embeddings=[genai_types.ContentEmbedding(values=item) for item in values])


def gemini_error(status: int, message: str = "provider message") -> Exception:
    error_class = genai_errors.ServerError if status >= 500 else genai_errors.ClientError
    return error_class(status, {"error": {"code": status, "message": message, "status": "TEST"}})


def gemini_transport_error(cls: type[httpx2.TransportError]) -> Exception:
    return cls("transport failure", request=httpx2.Request("POST", GEMINI_EMBED_URL))


def test_texts_are_embedded_with_the_configured_model_task_and_size(gemini: SimpleNamespace) -> None:
    gemini.outcomes.append(embeddings())
    assert embed(TEXTS, "RETRIEVAL_DOCUMENT") == [[0.5] * 768, [0.5] * 768]
    [client] = gemini.clients
    config = genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768)
    assert client.requests == [{"model": "gemini-embedding-001", "contents": TEXTS, "config": config}]


def test_the_embedding_client_is_pinned_to_gemini_with_its_key_and_timeout(gemini: SimpleNamespace) -> None:
    gemini.outcomes.append(embeddings(1))
    embed(["question"], "RETRIEVAL_QUERY", timeout=60)
    [client] = gemini.clients
    options = genai_types.HttpOptions(base_url=GEMINI_EMBED_URL, timeout=60_000)
    assert client.options == {"vertexai": False, "api_key": GEMINI_KEY, "http_options": options}
    assert client.requests[0]["config"].task_type == "RETRIEVAL_QUERY"


@pytest.mark.parametrize("task", ["SEMANTIC_SIMILARITY", "retrieval_query", ""])
def test_an_unknown_task_is_refused_before_any_request(gemini: SimpleNamespace, task: str) -> None:
    with pytest.raises(ValueError, match="task must be RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY"):
        embed(TEXTS, task)
    assert gemini.clients == []


def test_missing_embedding_settings_fail_before_any_request(
    gemini: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        embed(TEXTS, "RETRIEVAL_DOCUMENT")
    assert gemini.clients == []


@pytest.mark.parametrize(
    "error",
    [gemini_error(429), gemini_error(500), gemini_error(503), gemini_transport_error(httpx2.ReadTimeout)],
    ids=["429", "500", "503", "timeout"],
)
def test_a_transient_embedding_failure_is_retried_once(gemini: SimpleNamespace, error: Exception) -> None:
    gemini.outcomes.extend([error, embeddings()])
    assert len(embed(TEXTS, "RETRIEVAL_DOCUMENT")) == 2
    assert len(gemini.clients[0].requests) == 2
    assert gemini.sleeps == [RETRY_DELAY_SECONDS]


@pytest.mark.parametrize(
    ("error", "hint"),
    [
        (gemini_error(400), "HTTP 400, request rejected"),
        (gemini_error(401), "check GEMINI_API_KEY"),
        (gemini_error(403), "check GEMINI_API_KEY"),
        (gemini_error(404), "check EMBED_MODEL"),
        (gemini_transport_error(httpx2.ConnectError), "could not reach the Gemini API"),
    ],
    ids=["400", "401", "403", "404", "connect"],
)
def test_a_permanent_embedding_failure_is_not_retried(gemini: SimpleNamespace, error: Exception, hint: str) -> None:
    gemini.outcomes.append(error)
    with pytest.raises(ModelCallError, match=hint):
        embed(TEXTS, "RETRIEVAL_DOCUMENT")
    assert len(gemini.clients[0].requests) == 1
    assert gemini.sleeps == []


def test_a_second_transient_embedding_failure_ends_the_call(gemini: SimpleNamespace) -> None:
    gemini.outcomes.extend([gemini_transport_error(httpx2.ReadTimeout), gemini_error(503)])
    with pytest.raises(ModelCallError, match="Embedding model gemini-embedding-001 failed: HTTP 503, provider error"):
        embed(TEXTS, "RETRIEVAL_DOCUMENT")
    assert gemini.sleeps == [RETRY_DELAY_SECONDS]


@pytest.mark.parametrize(
    ("reply", "problem"),
    [
        (embeddings(1), r"wrong number of vectors \(1, expected 2\)"),
        (genai_types.EmbedContentResponse(embeddings=None), r"wrong number of vectors \(0, expected 2\)"),
        (embeddings(2, size=3072), r"size is not EMBED_DIM \(768\)"),
        (vectors([None, [0.5] * 768]), r"size is not EMBED_DIM \(768\)"),
        (vectors([[0.5] * 768, [0.5] * 767 + [math.nan]]), "not a finite number"),
        (vectors([[math.inf] + [0.5] * 767, [0.5] * 768]), "not a finite number"),
    ],
    ids=["too few", "none", "wrong size", "no values", "nan", "infinity"],
)
def test_a_reply_that_does_not_fit_the_texts_is_an_error(gemini: SimpleNamespace, reply: object, problem: str) -> None:
    gemini.outcomes.append(reply)
    with pytest.raises(ModelCallError, match=problem):
        embed(TEXTS, "RETRIEVAL_DOCUMENT")


def test_embedding_errors_and_logs_never_contain_the_key_or_the_texts(
    gemini: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    leaky = f"API key {GEMINI_KEY} rejected while embedding {TEXTS[0]}"
    gemini.outcomes.extend([gemini_error(429, leaky), gemini_error(400, leaky)])
    caplog.set_level(logging.WARNING, logger="llm.client")
    with pytest.raises(ModelCallError) as error:
        embed(TEXTS, "RETRIEVAL_DOCUMENT")
    assert "retrying once" in caplog.text
    for secret in (GEMINI_KEY, TEXTS[0]):
        assert secret not in str(error.value)
        assert secret not in caplog.text
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__


def test_the_real_embedding_client_cannot_reach_the_network_in_tests(blocked_network: list[object]) -> None:
    with pytest.raises(ModelCallError, match="could not reach the Gemini API"):
        embed(TEXTS, "RETRIEVAL_DOCUMENT")
    assert len(blocked_network) == 1
