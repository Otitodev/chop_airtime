from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    # LLM_PROVIDER controls which model is tried first.
    # Options: "openai" (default) | "mistral" | "anthropic"
    # On failure the agent falls back: openai → mistral → anthropic
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")
    # Mistral model name — override if you want mistral-small-latest etc.
    mistral_model: str = Field(default="mistral-large-latest", alias="MISTRAL_MODEL")

    # Database (Neon / any PostgreSQL)
    database_url: str = Field(..., alias="DATABASE_URL")

    # VTpass
    vtpass_api_key: str = Field(default="", alias="VTPASS_API_KEY")
    vtpass_secret_key: str = Field(default="", alias="VTPASS_SECRET_KEY")
    vtpass_base_url: str = Field(
        default="https://vtpass.com/api", alias="VTPASS_BASE_URL"
    )

    # VTU.ng fallback
    vtu_ng_jwt_token: str = Field(default="", alias="VTU_NG_JWT_TOKEN")
    vtu_ng_base_url: str = Field(
        default="https://vtu.ng/wp-json/vtu-ng/v1", alias="VTU_NG_BASE_URL"
    )

    # Evolution API (WhatsApp)
    evolution_api_webhook_secret: str = Field(
        default="", alias="EVOLUTION_API_WEBHOOK_SECRET"
    )
    evolution_api_url: str = Field(default="", alias="EVOLUTION_API_URL")
    evolution_api_instance: str = Field(default="", alias="EVOLUTION_API_INSTANCE")
    evolution_api_key: str = Field(default="", alias="EVOLUTION_API_KEY")

    # SMTP / Alerts
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_pass: str = Field(default="", alias="SMTP_PASS")
    alert_email_to: str = Field(default="", alias="ALERT_EMAIL_TO")
    slack_webhook_url: str = Field(default="", alias="SLACK_WEBHOOK_URL")

    # Business rules
    low_balance_threshold: float = Field(default=500.0, alias="LOW_BALANCE_THRESHOLD")
    user_lifetime_cap: float = Field(default=500.0, alias="USER_LIFETIME_CAP")
    min_topup: float = Field(default=50.0, alias="MIN_TOPUP")
    max_topup: float = Field(default=500.0, alias="MAX_TOPUP")

    # CORS
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
