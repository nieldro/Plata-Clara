import pytest
from pydantic import ValidationError

from app.config import DEV_SECRET, Settings


def test_production_rejects_default_or_short_secret():
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key=DEV_SECRET)
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key="corta")
    assert Settings(environment="production", secret_key="x" * 40).environment == "production"


def test_development_allows_default_secret():
    assert Settings(environment="development", secret_key=DEV_SECRET).secret_key == DEV_SECRET
