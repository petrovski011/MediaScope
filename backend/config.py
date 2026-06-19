from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediascope:devpassword@localhost:5432/mediascope"
    REDIS_URL: str = "redis://localhost:6379"

    SECRET_KEY: str = "dev_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5"

    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3001", "http://localhost:5174"]
    INTRADAY_EXCLUDED_SOURCES: List[str] = ["rts", "tanjug"]

    MAX_PER_PAGE: int = 100
    EXPORT_MAX_ROWS: int = 50000

    COPYPASTE_THRESHOLD: float = 0.85
    FRAMING_COORD_MIN_SCORE: float = 0.70
    NARRATIVE_COORD_MIN_SCORE: float = 0.75
    ANOMALY_DEVIATION_THRESHOLD: float = 2.0

    SQLITE_DB_PATH: str = "/data/mediascope.db"

    @field_validator("ALLOWED_ORIGINS", "INTRADAY_EXCLUDED_SOURCES", mode="before")
    @classmethod
    def parse_list(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                return json.loads(v)
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
