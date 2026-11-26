from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@db:5432/app"
    REDIS_URL: str = "redis://redis:6379/0"

    model_config = {"env_file": ".env"}


settings = Settings()
