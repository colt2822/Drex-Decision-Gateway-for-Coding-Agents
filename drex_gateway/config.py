"""Gateway configuration and safe credential resolution."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

DEFAULT_BASE_URL = "https://drex.nace.ai"
DEFAULT_MODEL = "drex-latest"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_DB_PATH = "drex_gateway.db"

_KEY_PATTERN = re.compile(r"nace_sk_[A-Za-z0-9_-]{43}\Z")


class PolicyConfig(BaseModel):
    accept_threshold: float = 0.85
    escalation_threshold: float = 0.60


class GatewayConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    base_url: str = Field(default=DEFAULT_BASE_URL)
    model: str = Field(default=DEFAULT_MODEL)
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS)
    db_path: str = Field(default=DEFAULT_DB_PATH)
    force_provider: Literal["LIVE", "REPLAY"] | None = Field(
        default=None, description="Force LIVE or REPLAY provider mode"
    )
    api_key_override: SecretStr | None = Field(default=None, exclude=True, repr=False)
    default_policy: PolicyConfig = Field(default_factory=PolicyConfig)
    decision_policies: dict[str, PolicyConfig] = Field(default_factory=dict)
    model_cost_table: dict[str, float] = Field(
        default_factory=lambda: {
            "claude-3-5-sonnet": 0.03,  # estimated benchmark cost per call ($)
            "gpt-4o": 0.025,
            "gemini-1-5-pro": 0.02,
        },
        description="Optional model cost per invocation table in USD",
    )

    @field_validator("force_provider", mode="before")
    @classmethod
    def normalize_force_provider(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @classmethod
    def from_env(cls) -> GatewayConfig:
        base_url = os.environ.get("DREX_BASE_URL", DEFAULT_BASE_URL)
        model = os.environ.get("DREX_MODEL", DEFAULT_MODEL)
        timeout_seconds = float(os.environ.get("DREX_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        db_path = os.environ.get("DREX_GATEWAY_DB", DEFAULT_DB_PATH)
        force_provider = os.environ.get("DREX_PROVIDER_MODE")  # LIVE or REPLAY

        config = cls(
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            db_path=db_path,
            force_provider=force_provider,
        )
        return config

    def get_api_key(self) -> str | None:
        """Safely resolve API key from environment variable or key file without printing."""
        if self.api_key_override is not None:
            key = self.api_key_override.get_secret_value().strip()
            return key if _KEY_PATTERN.fullmatch(key) else None

        # 1. Direct environment variable
        direct_key = os.environ.get("DREX_API_KEY", "").strip()
        if direct_key:
            if _KEY_PATTERN.fullmatch(direct_key):
                return direct_key

        # 2. File path
        key_path = os.environ.get("DREX_API_KEY_FILE")
        if not key_path:
            # Standard default user locations
            for cand in [
                Path.home() / ".config" / "drex" / "api.key",
                Path.home() / ".drex" / "api.key",
            ]:
                if cand.is_file():
                    key_path = str(cand)
                    break

        if key_path:
            p = Path(key_path)
            if p.is_file():
                try:
                    mode = p.stat().st_mode
                    # Check that permissions are restricted (no world/group read)
                    if mode & 0o077 == 0:
                        content = p.read_text(encoding="utf-8").strip()
                        if _KEY_PATTERN.fullmatch(content):
                            return content
                except OSError:
                    pass

        return None

    def has_live_credentials(self) -> bool:
        return self.get_api_key() is not None

    def get_policy(self, decision_type: str) -> PolicyConfig:
        if decision_type in self.decision_policies:
            return self.decision_policies[decision_type]
        return self.default_policy
