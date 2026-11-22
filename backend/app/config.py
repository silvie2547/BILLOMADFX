from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "BILLOMADFX"
    environment: str = "development"
    app_version: str = "0.0.1"
    database_url: str = "sqlite:///./data/billomadfx.db"
    app_secret_key: str = "development-only-change-this-secret-before-deploying"
    access_token_minutes: int = 43200  # 30 days; the client renews it on use (sliding session)
    cors_origins: str = (
        "http://localhost:8000,http://127.0.0.1:8000,"
        "http://localhost:8080,http://127.0.0.1:8080,"
        "https://localhost,capacitor://localhost,ionic://localhost"
    )
    static_dir: str = "../web_app"
    # When the frontend is hosted on a different origin than the API, list the
    # API origin(s) here so the Content-Security-Policy connect-src allows them.
    csp_extra_connect_srcs: str = ""
    # Read the real client IP from X-Forwarded-For (set by Render, nginx, etc.).
    # Disable only when running directly exposed without a reverse proxy.
    trust_forwarded_for: bool = True

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def csp_connect_srcs(self) -> list[str]:
        return [origin.strip() for origin in self.csp_extra_connect_srcs.split(",") if origin.strip()]

    def validate_deployment(self) -> None:
        if self.environment.lower() == "production":
            if self.app_secret_key == "development-only-change-this-secret-before-deploying":
                raise RuntimeError("APP_SECRET_KEY must be set to a unique secret in production")
            if self.database_url.startswith("sqlite"):
                raise RuntimeError("Configure a managed PostgreSQL DATABASE_URL in production")


settings = Settings()
settings.validate_deployment()
