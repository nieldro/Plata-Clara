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
    # Límite de intentos (ver services/ratelimit.py)
    login_max_failures: int = 5          # fallos permitidos por IP + correo en la ventana
    login_ip_max_failures: int = 30      # fallos permitidos por IP (cualquier correo)
    login_window_seconds: int = 15 * 60
    register_max_per_hour: int = 10

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
