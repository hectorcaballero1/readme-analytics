from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8005
    JWT_SECRET: str
    ALLOWED_ORIGINS: str = ""
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_SESSION_TOKEN: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    ATHENA_DATABASE: str = "readme_db"
    ATHENA_OUTPUT_BUCKET: str

    model_config = {"env_file": ".env"}


settings = Settings()
