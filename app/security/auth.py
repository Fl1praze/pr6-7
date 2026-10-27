import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

ACCESS_TOKEN_EXPIRE_MINUTES = 60
ACCESS_TOKEN_COOKIE = "recruitment_access_token"


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        # Поврежденный или пустой хэш в БД не должен приводить к ошибке 500
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": now,
        "type": "access",
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


class LoginRateLimiter:
    """Ограничение числа неудачных попыток входа (защита от перебора пароля).

    Аналог LOGIN_LIMIT = "5/minute" из NewFastAPI, без внешних зависимостей.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._failures: dict[str, deque] = defaultdict(deque)

    def _cleanup(self, key: str) -> deque:
        attempts = self._failures[key]
        border = time.monotonic() - self.window
        while attempts and attempts[0] < border:
            attempts.popleft()
        return attempts

    def is_blocked(self, key: str) -> bool:
        return len(self._cleanup(key)) >= self.max_attempts

    def register_failure(self, key: str) -> None:
        self._cleanup(key).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


login_limiter = LoginRateLimiter()
