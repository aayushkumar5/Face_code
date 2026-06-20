"""Environment-driven application configuration."""

import os
from dataclasses import dataclass
from pathlib import Path


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value")


def _positive_integer(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    environment: str
    secret_key: str
    require_session_auth: bool
    allow_local_code_execution: bool
    cors_origins: tuple[str, ...]
    trusted_hosts: tuple[str, ...]
    database_path: Path
    max_request_bytes: int
    session_ttl_seconds: int
    log_level: str
    runner_url: str
    runner_secret: str
    retention_days: int

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @classmethod
    def from_env(cls, project_root: Path) -> "Settings":
        environment = os.getenv("FACECODE_ENV", "development").strip().lower()
        if environment not in {"development", "test", "production"}:
            raise RuntimeError(
                "FACECODE_ENV must be development, test, or production"
            )
        production = environment == "production"
        secret = os.getenv("FACECODE_SECRET_KEY", "development-only-secret")
        if production and (len(secret) < 32 or secret.startswith("replace-with-")):
            raise RuntimeError("FACECODE_SECRET_KEY must contain at least 32 characters")
        runner_url = os.getenv("FACECODE_RUNNER_URL", "").rstrip("/")
        runner_secret = os.getenv("FACECODE_RUNNER_SECRET", "")
        require_session_auth = _boolean("FACECODE_REQUIRE_SESSION_AUTH", production)
        allow_local_execution = _boolean(
            "FACECODE_ALLOW_LOCAL_CODE_EXECUTION", not production
        )
        if production and not runner_url:
            raise RuntimeError("FACECODE_RUNNER_URL is required in production")
        if runner_url and not runner_url.startswith(("http://", "https://")):
            raise RuntimeError("FACECODE_RUNNER_URL must use http:// or https://")
        if production and (
            len(runner_secret) < 32 or runner_secret.startswith("replace-with-")
        ):
            raise RuntimeError("FACECODE_RUNNER_SECRET must contain at least 32 characters")
        if production and runner_secret == secret:
            raise RuntimeError("Session and runner secrets must be different")
        if production and not require_session_auth:
            raise RuntimeError("Session authentication cannot be disabled in production")
        if production and allow_local_execution:
            raise RuntimeError("Local code execution cannot be enabled in production")

        data_dir = Path(os.getenv("FACECODE_DATA_DIR", str(project_root / "data")))
        data_dir.mkdir(parents=True, exist_ok=True)
        legacy_database = project_root / "facecode.db"
        default_database = (
            legacy_database if not production and legacy_database.exists()
            else data_dir / "facecode.db"
        )
        origins = os.getenv(
            "FACECODE_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
        hosts = os.getenv("FACECODE_TRUSTED_HOSTS", "localhost,127.0.0.1")
        log_level = os.getenv("FACECODE_LOG_LEVEL", "INFO").upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise RuntimeError("FACECODE_LOG_LEVEL is invalid")
        return cls(
            environment=environment,
            secret_key=secret,
            require_session_auth=require_session_auth,
            allow_local_code_execution=allow_local_execution,
            cors_origins=tuple(item.strip() for item in origins.split(",") if item.strip()),
            trusted_hosts=tuple(item.strip() for item in hosts.split(",") if item.strip()),
            database_path=Path(
                os.getenv("FACECODE_DATABASE_PATH", str(default_database))
            ),
            max_request_bytes=_positive_integer(
                "FACECODE_MAX_REQUEST_BYTES", 4_000_000, 1_000_000
            ),
            session_ttl_seconds=_positive_integer(
                "FACECODE_SESSION_TTL_SECONDS", 21_600, 300
            ),
            log_level=log_level,
            runner_url=runner_url,
            runner_secret=runner_secret,
            retention_days=_positive_integer("FACECODE_RETENTION_DAYS", 30),
        )
