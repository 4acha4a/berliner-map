from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.privacy import register_database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: SecretStr = SecretStr("postgresql+psycopg://berliner:berliner@localhost:5432/berliner_map")

    def model_post_init(self, context):
        register_database_url(self.database_url.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
