"""Configuración de la aplicación (pydantic-settings, lee de .env)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # App
    app_name: str = "WC Oracle 2026"
    environment: str = "development"
    debug: bool = True

    # Seguridad / JWT
    secret_key: str = "dev-insecure-change-me"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Admin semilla
    admin_username: str = "admin"
    admin_password: str = "admin"
    admin_email: str = "admin@local"

    # Base de datos
    database_url: str = "sqlite:///./data/app.db"

    # CORS (vacío si se usa reverse-proxy de entrada única)
    cors_origins: str = ""

    # Fuentes de datos
    results_csv_url: str = (
        "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
    )
    shootouts_csv_url: str = (
        "https://raw.githubusercontent.com/martj42/international_results/master/shootouts.csv"
    )
    api_football_key: str = ""
    api_football_base: str = "https://v3.football.api-sports.io"
    football_data_org_token: str = ""
    football_data_org_base: str = "https://api.football-data.org/v4"
    football_data_competition: str = "WC"  # código del Mundial en football-data.org

    # Sincronización en vivo (scheduler). Solo se activa si hay API key.
    live_sync_interval_minutes: int = 15

    # Simulación
    monte_carlo_runs: int = 10000

    # Despliegue
    servidor_a_ip: str = "192.168.1.50"
    servidor_a_port: int = 8000

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
