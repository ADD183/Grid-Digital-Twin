"""Environment-driven configuration for the additive backend services."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Validated service settings with safe local-development defaults."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "production"] = Field(
        default="development", validation_alias="ENV"
    )
    port: int = Field(default=8000, ge=1, le=65535, validation_alias="PORT")
    openrouter_api_key: SecretStr | None = Field(
        default=None,
        repr=False,
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY"),
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"
    grid_api_url: str | None = None
    telemetry_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    telemetry_poll_seconds: float = Field(default=60.0, gt=0, le=3600)
    telemetry_stale_after_seconds: float = Field(default=300.0, gt=0)
    replan_drift_threshold: float = Field(default=0.15, ge=0, le=1)
    solver_tolerance: float = Field(default=1e-6, gt=0)
    voltage_min_pu: float = Field(default=0.95, gt=0)
    voltage_max_pu: float = Field(default=1.05, gt=0)
    max_line_loading_percent: float = Field(default=100.0, gt=0)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    artifacts_dir: Path = PROJECT_ROOT / "artifacts"
    surrogate_model_path: Path = PROJECT_ROOT / "backend" / "models" / "surrogate.joblib"
    telemetry_mock_seed: int = Field(default=42, ge=0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("voltage_max_pu")
    @classmethod
    def validate_voltage_band(cls, value: float, info: object) -> float:
        minimum = getattr(info, "data", {}).get("voltage_min_pu", 0.95)
        if value <= minimum:
            raise ValueError("voltage_max_pu must be greater than voltage_min_pu")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()