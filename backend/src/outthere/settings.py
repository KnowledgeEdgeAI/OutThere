from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OUTTHERE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/outthere.db"
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    access_token_seconds: int = Field(default=900, ge=60, le=86400)
    refresh_token_seconds: int = Field(default=30 * 86400, ge=3600)
    sync_poll_seconds: float = Field(default=1.0, ge=0.05, le=30)
    maps_provider: Literal["disabled", "google"] = "disabled"
    google_maps_api_key: SecretStr = SecretStr("")
    auth_mode: Literal["disabled", "unverified_phone"] = "disabled"
    auth_retry_key: SecretStr = SecretStr("")
    auth_retry_seconds: int = Field(default=300, ge=60, le=3600)
    action_retry_seconds: int = Field(default=7 * 86400, ge=60, le=7 * 86400)

    media_directory: str = "./data/media"

    match_jitter_seconds: int = Field(default=30, ge=0, le=300)

    fcm_service_account: SecretStr = SecretStr("")
    apns_private_key: SecretStr = SecretStr("")
    apns_key_id: str = ""
    apns_team_id: str = ""
    apns_topic: str = ""
    apns_sandbox: bool = True
