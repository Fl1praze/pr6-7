from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    SECRET_KEY: str
    ALGORITHM: str

    REDIS_HOST: str
    REDIS_PORT: int

    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str

    model_config = SettingsConfigDict(env_file=".env")

    @field_validator("SECRET_KEY")
    @classmethod
    def check_secret_key(cls, v: str) -> str:
        # Короткий ключ позволяет подобрать подпись и подделать JWT
        if len(v) < 32:
            raise ValueError("SECRET_KEY должен содержать не менее 32 символов")
        return v

    @field_validator("ALGORITHM")
    @classmethod
    def check_algorithm(cls, v: str) -> str:
        if v not in ("HS256", "HS384", "HS512"):
            raise ValueError("ALGORITHM должен быть HS256, HS384 или HS512")
        return v

    @field_validator("DB_PORT", "REDIS_PORT", "MAIL_PORT")
    @classmethod
    def check_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("порт должен быть в диапазоне 1–65535")
        return v

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
