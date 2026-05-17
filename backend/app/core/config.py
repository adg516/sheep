from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_password: str = Field(default="change-me", alias="APP_PASSWORD")
    database_url: str = Field(default="sqlite:///./command_card.db", alias="DATABASE_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
