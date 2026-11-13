import os
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from urllib.parse import urlsplit

# The environment variable prefix for each model role (BLUEPRINT 8.4).
MODEL_ROLES = {"writer": "CHAT", "judge": "JUDGE"}
# CLAUDE.md approves Groq and Gemini only; another provider needs the owner's approval.
APPROVED_MODEL_HOSTS = {"api.groq.com", "generativelanguage.googleapis.com"}
# db/schema.sql stores embeddings as vector(768).
SCHEMA_EMBED_DIM = 768


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    chat_base_url: str
    chat_api_key: str = field(repr=False)
    chat_model: str
    judge_base_url: str
    judge_api_key: str = field(repr=False)
    judge_model: str
    gemini_api_key: str = field(repr=False)
    embed_model: str
    embed_dim: int
    kb_dir: str
    daily_token_budget: int


def load_settings(environ: Mapping[str, str] = os.environ) -> Settings:
    """Build Settings from the environment, failing once with every missing or empty variable named."""
    missing = [item.name.upper() for item in fields(Settings) if not environ.get(item.name.upper())]
    if missing:
        raise RuntimeError(f"Set these environment variables (see .env.example): {', '.join(missing)}")
    return Settings(
        database_url=environ["DATABASE_URL"],
        chat_base_url=environ["CHAT_BASE_URL"],
        chat_api_key=environ["CHAT_API_KEY"],
        chat_model=environ["CHAT_MODEL"],
        judge_base_url=environ["JUDGE_BASE_URL"],
        judge_api_key=environ["JUDGE_API_KEY"],
        judge_model=environ["JUDGE_MODEL"],
        gemini_api_key=environ["GEMINI_API_KEY"],
        embed_model=environ["EMBED_MODEL"],
        embed_dim=read_int(environ, "EMBED_DIM"),
        kb_dir=environ["KB_DIR"],
        daily_token_budget=read_int(environ, "DAILY_TOKEN_BUDGET"),
    )


def read_int(environ: Mapping[str, str], name: str) -> int:
    try:
        return int(environ[name])
    except ValueError:
        raise RuntimeError(f"{name} must be a whole number.") from None


@dataclass(frozen=True)
class ModelEndpoint:
    role: str
    base_url: str
    api_key: str = field(repr=False)
    model: str


def model_endpoint(model: str, environ: Mapping[str, str] = os.environ) -> ModelEndpoint:
    """The writer (CHAT_*) or judge (JUDGE_*) endpoint configured for `model`; never the other role's."""
    roles = [role for role, prefix in MODEL_ROLES.items() if model and environ.get(f"{prefix}_MODEL") == model]
    if not roles:
        raise RuntimeError(f"Model {model!r} matches neither CHAT_MODEL nor JUDGE_MODEL (see .env.example).")
    if len(roles) > 1:
        raise RuntimeError("CHAT_MODEL and JUDGE_MODEL must differ: the judge must not grade its own answers.")
    prefix = MODEL_ROLES[roles[0]]
    missing = [name for name in (f"{prefix}_BASE_URL", f"{prefix}_API_KEY") if not environ.get(name)]
    if missing:
        raise RuntimeError(f"Set these environment variables (see .env.example): {', '.join(missing)}")
    base_url = environ[f"{prefix}_BASE_URL"]
    url = urlsplit(base_url)
    if url.scheme != "https" or url.hostname not in APPROVED_MODEL_HOSTS:
        raise RuntimeError(f"{prefix}_BASE_URL must be an https URL on {' or '.join(sorted(APPROVED_MODEL_HOSTS))}.")
    return ModelEndpoint(roles[0], base_url, environ[f"{prefix}_API_KEY"], model)


def writer_model(environ: Mapping[str, str] = os.environ) -> str:
    """CHAT_MODEL, once its endpoint settings are complete and on an approved host."""
    require(environ, "CHAT_MODEL")
    return model_endpoint(environ["CHAT_MODEL"], environ).model


@dataclass(frozen=True)
class EmbeddingSettings:
    api_key: str = field(repr=False)
    model: str
    dim: int


def embedding_settings(environ: Mapping[str, str] = os.environ) -> EmbeddingSettings:
    require(environ, "GEMINI_API_KEY", "EMBED_MODEL", "EMBED_DIM")
    dim = read_int(environ, "EMBED_DIM")
    if dim != SCHEMA_EMBED_DIM:
        raise RuntimeError(f"EMBED_DIM must be {SCHEMA_EMBED_DIM}, the vector size in db/schema.sql.")
    return EmbeddingSettings(environ["GEMINI_API_KEY"], environ["EMBED_MODEL"], dim)


def database_url(environ: Mapping[str, str] = os.environ) -> str:
    require(environ, "DATABASE_URL")
    return environ["DATABASE_URL"]


def kb_dir(environ: Mapping[str, str] = os.environ) -> str:
    require(environ, "KB_DIR")
    return environ["KB_DIR"]


def require(environ: Mapping[str, str], *names: str) -> None:
    missing = [name for name in names if not environ.get(name)]
    if missing:
        raise RuntimeError(f"Set these environment variables (see .env.example): {', '.join(missing)}")
