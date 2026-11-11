import pytest

from config import load_settings

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
