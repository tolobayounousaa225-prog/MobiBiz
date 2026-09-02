from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{BASE_DIR / 'mobibiz_dev.db'}"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5510,http://127.0.0.1:5510"
    max_upload_size_mb: int = 5
    # Origine du frontend déployé — utilisée uniquement pour construire l'URL de
    # vérification encodée dans les QR de certification (factures, reçus). Pas
    # d'usage en local par défaut : les tests locaux vérifient l'API directement.
    frontend_base_url: str = "https://tolobayounousaa225-prog.github.io/MobiBiz"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
