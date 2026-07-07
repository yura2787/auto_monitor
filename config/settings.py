from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    POSTGRES_URL: str
    REDIS_URL: str = "redis://redis:6379/0"
    PRICE_DROP_THRESHOLD: int = 10
    CHECK_INTERVAL: int = 120
    OLX_BASE_URL: str = "https://www.olx.ua/uk/transport/legkovye-avtomobili/"
    MAX_PAGES: int = 3
    PHOTOS_LIMIT: int = 4
    MARKET_SAMPLE_SIZE: int = 50
    DAILY_STATS_HOUR: int = 20
    CLEANUP_DAYS: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
