from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    secret_key: str = "dev-only-change-me"
    token_minutes: int = 60 * 12


settings = Settings()
