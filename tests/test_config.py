import pytest

from config import load_settings, model_endpoint

ENVIRONMENT = {
    "DATABASE_URL": "postgresql://app:db-secret@db.example.com:5432/postgres",
    "CHAT_BASE_URL": "https://chat.example.com/v1",
    "CHAT_API_KEY": "chat-secret",
    "CHAT_MODEL": "chat-model",
    "JUDGE_BASE_URL": "https://judge.example.com/v1",
    "JUDGE_API_KEY": "judge-secret",
    "JUDGE_MODEL": "judge-model",
    "GEMINI_API_KEY": "gemini-secret",
    "EMBED_MODEL": "gemini-embedding-001",
    "EMBED_DIM": "768",
    "KB_DIR": "kb",
    "DAILY_TOKEN_BUDGET": "400000",
}


def test_complete_environment_loads_integer_settings() -> None:
    settings = load_settings(ENVIRONMENT)
    assert settings.embed_dim == 768
    assert settings.daily_token_budget == 400000


def test_every_missing_or_empty_variable_is_named() -> None:
    environ = ENVIRONMENT | {"CHAT_API_KEY": ""}
    del environ["JUDGE_MODEL"]
    with pytest.raises(RuntimeError) as error:
        load_settings(environ)
    assert "CHAT_API_KEY" in str(error.value)
    assert "JUDGE_MODEL" in str(error.value)


def test_bad_integer_names_the_variable_but_not_its_value() -> None:
    with pytest.raises(RuntimeError) as error:
        load_settings(ENVIRONMENT | {"EMBED_DIM": "seven"})
    assert "EMBED_DIM" in str(error.value)
    assert "seven" not in str(error.value)


def test_repr_hides_credentials() -> None:
    text = repr(load_settings(ENVIRONMENT))
    for secret in ("db-secret", "chat-secret", "judge-secret", "gemini-secret"):
        assert secret not in text


MODELS = {
    "CHAT_BASE_URL": "https://api.groq.com/openai/v1",
    "CHAT_API_KEY": "chat-secret",
    "CHAT_MODEL": "writer-model",
    "JUDGE_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "JUDGE_API_KEY": "judge-secret",
    "JUDGE_MODEL": "judge-model",
}


def test_each_model_is_routed_to_its_own_role() -> None:
    writer = model_endpoint("writer-model", MODELS)
    judge = model_endpoint("judge-model", MODELS)
    assert (writer.role, writer.base_url, writer.api_key) == ("writer", MODELS["CHAT_BASE_URL"], "chat-secret")
    assert (judge.role, judge.base_url, judge.api_key) == ("judge", MODELS["JUDGE_BASE_URL"], "judge-secret")


def test_writer_endpoint_needs_only_the_writer_variables() -> None:
    writer_only = {name: value for name, value in MODELS.items() if name.startswith("CHAT_")}
    assert model_endpoint("writer-model", writer_only).role == "writer"


def test_an_unconfigured_model_is_refused_without_a_fallback() -> None:
    with pytest.raises(RuntimeError, match="matches neither CHAT_MODEL nor JUDGE_MODEL"):
        model_endpoint("other-model", MODELS)


def test_writer_and_judge_must_use_different_models() -> None:
    with pytest.raises(RuntimeError, match="must differ"):
        model_endpoint("writer-model", MODELS | {"JUDGE_MODEL": "writer-model"})


def test_missing_endpoint_variables_are_all_named() -> None:
    with pytest.raises(RuntimeError) as error:
        model_endpoint("judge-model", MODELS | {"JUDGE_BASE_URL": "", "JUDGE_API_KEY": ""})
    assert "JUDGE_BASE_URL" in str(error.value)
    assert "JUDGE_API_KEY" in str(error.value)


@pytest.mark.parametrize("base_url", ["http://api.groq.com/openai/v1", "https://api.openai.com/v1", "api.groq.com"])
def test_base_url_must_be_https_on_an_approved_provider(base_url: str) -> None:
    with pytest.raises(RuntimeError, match="must be an https URL"):
        model_endpoint("writer-model", MODELS | {"CHAT_BASE_URL": base_url})


def test_endpoint_repr_hides_the_api_key() -> None:
    assert "chat-secret" not in repr(model_endpoint("writer-model", MODELS))
