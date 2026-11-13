import logging
import math
import time
from dataclasses import dataclass

import httpx2
import openai
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from openai.types.chat import ChatCompletion

from config import MODEL_ROLES, ModelEndpoint, embedding_settings, model_endpoint

# BLUEPRINT 11.3: retry once, and only after a 429, a 5xx or a timeout. There is no provider fallback.
TRANSIENT_ERRORS = (openai.RateLimitError, openai.InternalServerError, openai.APITimeoutError)
RETRY_DELAY_SECONDS = 2.0
# BLUEPRINT 11.4: documents and questions are embedded with different task types.
EMBED_TASKS = ("RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY")
GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Reply:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: int
    finish_reason: str | None = None  # as the provider sent it; only "stop" confirms a complete reply
    attempts: int = 1  # provider requests behind this reply: 2 after a retry


class ModelCallError(Exception):
    """A model call that failed. The message names the model and the reason, never the key or the input."""


def chat(
    messages: list[dict[str, str]], model: str, max_tokens: int, temperature: float, timeout: float = 30.0
) -> Reply:
    """Send one chat request to the endpoint configured for `model`; raise ModelCallError when it fails."""
    endpoint = model_endpoint(model)
    request = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    started = time.perf_counter()
    with openai.OpenAI(
        base_url=endpoint.base_url, api_key=endpoint.api_key, timeout=timeout, max_retries=0
    ) as client:
        response, attempts = complete(client, endpoint, request, timeout)
    # Token counts feed the daily budget, so a reply without them is an error, not zero tokens.
    if not response.choices or response.usage is None:
        raise ModelCallError(f"{describe(endpoint)} returned no choices or no token usage.")
    return Reply(
        text=response.choices[0].message.content or "",
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        model=response.model,
        latency_ms=round((time.perf_counter() - started) * 1000),
        finish_reason=response.choices[0].finish_reason,
        attempts=attempts,
    )


def complete(
    client: openai.OpenAI, endpoint: ModelEndpoint, request: dict[str, object], timeout: float
) -> tuple[ChatCompletion, int]:
    """Send the request, and once more after a transient failure. Also return how many requests were sent."""
    try:
        return client.chat.completions.create(**request), 1
    except TRANSIENT_ERRORS as error:
        logger.warning("%s; retrying once", failure(endpoint, error, timeout))
    except openai.APIError as error:
        raise ModelCallError(failure(endpoint, error, timeout)) from None
    time.sleep(RETRY_DELAY_SECONDS)
    try:
        return client.chat.completions.create(**request), 2
    except openai.APIError as error:
        raise ModelCallError(failure(endpoint, error, timeout)) from None


def failure(endpoint: ModelEndpoint, error: openai.APIError, timeout: float) -> str:
    """Why a call failed. The provider's own message is left out because it can quote part of the key."""
    prefix = MODEL_ROLES[endpoint.role]
    if isinstance(error, openai.APITimeoutError):
        reason = f"timed out after {timeout:g} s"
    elif isinstance(error, openai.APIStatusError):
        reason = status_reason(error.status_code, f"{prefix}_API_KEY", f"{prefix}_MODEL and {prefix}_BASE_URL")
    else:
        reason = f"could not reach {prefix}_BASE_URL"
    return f"{describe(endpoint)} failed: {reason}"


def status_reason(status: int, key_setting: str, model_settings: str) -> str:
    if status in (401, 403):
        return f"HTTP {status}, authentication failed; check {key_setting}"
    if status == 404:
        return f"HTTP 404, model or endpoint not found; check {model_settings}"
    if status == 429:
        return "HTTP 429, rate limited"
    if status >= 500:
        return f"HTTP {status}, provider error"
    return f"HTTP {status}, request rejected"


def describe(endpoint: ModelEndpoint) -> str:
    return f"{endpoint.role.capitalize()} model {endpoint.model}"


def embed(texts: list[str], task: str, timeout: float = 30.0) -> list[list[float]]:
    """One vector per text from the Gemini embedding model; raise ModelCallError when the call or its reply fails."""
    if task not in EMBED_TASKS:
        raise ValueError(f"task must be {' or '.join(EMBED_TASKS)}, not {task!r}.")
    settings = embedding_settings()
    request = {
        "model": settings.model,
        "contents": texts,
        "config": genai_types.EmbedContentConfig(task_type=task, output_dimensionality=settings.dim),
    }
    # A fixed host and vertexai=False keep GOOGLE_* variables from sending the key to another endpoint.
    options = genai_types.HttpOptions(base_url=GEMINI_EMBED_URL, timeout=round(timeout * 1000))
    with genai.Client(vertexai=False, api_key=settings.api_key, http_options=options) as client:
        response = embed_content(client, request, timeout)
    vectors = [item.values or [] for item in response.embeddings or []]
    if len(vectors) != len(texts):
        raise ModelCallError(
            f"Embedding model {settings.model} returned the wrong number of vectors ({len(vectors)}, expected {len(texts)})."
        )
    if any(len(vector) != settings.dim for vector in vectors):
        raise ModelCallError(
            f"Embedding model {settings.model} returned a vector whose size is not EMBED_DIM ({settings.dim})."
        )
    # pgvector would reject these too, but only later and as a database error.
    if not all(math.isfinite(value) for vector in vectors for value in vector):
        raise ModelCallError(f"Embedding model {settings.model} returned a value that is not a finite number.")
    return vectors


def embed_content(
    client: genai.Client, request: dict[str, object], timeout: float
) -> genai_types.EmbedContentResponse:
    """Send the request, and once more after a 429, a 5xx or a timeout."""
    try:
        return client.models.embed_content(**request)
    except (genai_errors.APIError, httpx2.TransportError) as error:
        if not embed_transient(error):
            raise ModelCallError(embed_failure(request["model"], error, timeout)) from None
        logger.warning("%s; retrying once", embed_failure(request["model"], error, timeout))
    time.sleep(RETRY_DELAY_SECONDS)
    try:
        return client.models.embed_content(**request)
    except (genai_errors.APIError, httpx2.TransportError) as error:
        raise ModelCallError(embed_failure(request["model"], error, timeout)) from None


def embed_transient(error: Exception) -> bool:
    if isinstance(error, genai_errors.APIError):
        return error.code == 429 or error.code >= 500
    return isinstance(error, httpx2.TimeoutException)


def embed_failure(model: object, error: Exception, timeout: float) -> str:
    """Why an embedding call failed, without the provider's message, which can quote the input."""
    if isinstance(error, httpx2.TimeoutException):
        reason = f"timed out after {timeout:g} s"
    elif isinstance(error, genai_errors.APIError):
        reason = status_reason(error.code, "GEMINI_API_KEY", "EMBED_MODEL")
    else:
        reason = "could not reach the Gemini API"
    return f"Embedding model {model} failed: {reason}"
