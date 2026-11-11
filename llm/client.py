import logging
import time
from dataclasses import dataclass

import openai
from openai.types.chat import ChatCompletion

from config import MODEL_ROLES, ModelEndpoint, model_endpoint

# BLUEPRINT 11.3: retry once, and only after a 429, a 5xx or a timeout. There is no provider fallback.
TRANSIENT_ERRORS = (openai.RateLimitError, openai.InternalServerError, openai.APITimeoutError)
RETRY_DELAY_SECONDS = 2.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Reply:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: int


class ModelCallError(Exception):
    """A chat call that failed. The message names the role, model and status, never the key or the prompt."""


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
        response = complete(client, endpoint, request, timeout)
    # Token counts feed the daily budget, so a reply without them is an error, not zero tokens.
    if not response.choices or response.usage is None:
        raise ModelCallError(f"{describe(endpoint)} returned no choices or no token usage.")
    return Reply(
        text=response.choices[0].message.content or "",
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        model=response.model,
        latency_ms=round((time.perf_counter() - started) * 1000),
    )


def complete(
    client: openai.OpenAI, endpoint: ModelEndpoint, request: dict[str, object], timeout: float
) -> ChatCompletion:
    """Send the request, and once more after a transient failure."""
    try:
        return client.chat.completions.create(**request)
    except TRANSIENT_ERRORS as error:
        logger.warning("%s; retrying once", failure(endpoint, error, timeout))
    except openai.APIError as error:
        raise ModelCallError(failure(endpoint, error, timeout)) from None
    time.sleep(RETRY_DELAY_SECONDS)
    try:
        return client.chat.completions.create(**request)
    except openai.APIError as error:
        raise ModelCallError(failure(endpoint, error, timeout)) from None


def failure(endpoint: ModelEndpoint, error: openai.APIError, timeout: float) -> str:
    """Why a call failed. The provider's own message is left out because it can quote part of the key."""
    prefix = MODEL_ROLES[endpoint.role]
    if isinstance(error, openai.APITimeoutError):
        reason = f"timed out after {timeout:g} s"
    elif isinstance(error, openai.APIStatusError):
        reason = status_reason(error.status_code, prefix)
    else:
        reason = f"could not reach {prefix}_BASE_URL"
    return f"{describe(endpoint)} failed: {reason}"


def status_reason(status: int, prefix: str) -> str:
    if status in (401, 403):
        return f"HTTP {status}, authentication failed; check {prefix}_API_KEY"
    if status == 404:
        return f"HTTP 404, model or endpoint not found; check {prefix}_MODEL and {prefix}_BASE_URL"
    if status == 429:
        return "HTTP 429, rate limited"
    if status >= 500:
        return f"HTTP {status}, provider error"
    return f"HTTP {status}, request rejected"


def describe(endpoint: ModelEndpoint) -> str:
    return f"{endpoint.role.capitalize()} model {endpoint.model}"
