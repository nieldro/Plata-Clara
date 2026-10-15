from pydantic import model_validator
from pydantic_settings import BaseSettings

DEV_SECRET = "dev-only-change-me"
MIN_SECRET_LEN = 32


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    secret_key: str = DEV_SECRET
    token_minutes: int = 60 * 12
    environment: str = "development"  # production → exige configuración segura
    upload_dir: str = "uploads"
    max_upload_mb: int = 5

    @model_validator(mode="after")
    def _require_real_secret_in_production(self):
        if self.environment == "production" and (
            self.secret_key == DEV_SECRET or len(self.secret_key) < MIN_SECRET_LEN
        ):
            raise ValueError(
                "SECRET_KEY insegura: en producción define una clave aleatoria de al menos "
                f"{MIN_SECRET_LEN} caracteres (python -c \"import secrets; print(secrets.token_hex(32))\")"
            )
        return self


settings = Settings()
