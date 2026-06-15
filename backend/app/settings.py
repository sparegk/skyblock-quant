"""Runtime configuration for SkyBlock Quant services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "skyblock_quant.db"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_CORS_ORIGINS = "http://127.0.0.1:5173,http://localhost:5173"


@dataclass(frozen=True)
class DatabaseConfig:
    """Database settings derived from environment variables."""

    backend: str
    sqlite_path: Path
    database_url: str | None

    @property
    def is_sqlite(self) -> bool:
        return self.backend == "sqlite"

    @property
    def is_postgres(self) -> bool:
        return self.backend == "postgres"


def get_database_config() -> DatabaseConfig:
    """Return database config while keeping SQLite as the local default."""
    database_url = os.getenv("SKYBLOCK_QUANT_DATABASE_URL")
    sqlite_path = Path(os.getenv("SKYBLOCK_QUANT_DB_PATH", str(DEFAULT_SQLITE_PATH)))

    if database_url:
        normalized = database_url.lower()
        if normalized.startswith(("postgres://", "postgresql://")):
            return DatabaseConfig(
                backend="postgres",
                sqlite_path=sqlite_path,
                database_url=database_url,
            )

        if normalized.startswith("sqlite:///"):
            return DatabaseConfig(
                backend="sqlite",
                sqlite_path=Path(database_url.removeprefix("sqlite:///")),
                database_url=database_url,
            )

        raise ValueError(
            "SKYBLOCK_QUANT_DATABASE_URL must start with postgresql://, "
            "postgres://, or sqlite:///."
        )

    return DatabaseConfig(
        backend="sqlite",
        sqlite_path=sqlite_path,
        database_url=None,
    )


def get_cors_origins() -> list[str]:
    origins = os.getenv("SKYBLOCK_QUANT_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def get_raw_dir() -> Path:
    return Path(os.getenv("SKYBLOCK_QUANT_RAW_DIR", str(DEFAULT_RAW_DIR)))


def get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}
