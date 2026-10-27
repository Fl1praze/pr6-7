import logging

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session
from app.security.auth import ACCESS_TOKEN_COOKIE
from app.users.dao import UserDAO
from app.users.models import User
from app.validation import ADMIN_ROLE, HR_ROLES

logger = logging.getLogger("gribhh.auth")


def get_token(request: Request) -> str:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        # /auth/login возвращает токен и в теле ответа, поэтому принимаем и заголовок
        auth_header = request.headers.get("Authorization", "")
        scheme, _, value = auth_header.partition(" ")
        if scheme.lower() == "bearer" and value:
            token = value.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен отсутствует")
    return token


async def get_current_user(
        token: str = Depends(get_token),
        session: AsyncSession = Depends(get_async_session)
) -> User:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        logger.warning("[WARN] токен отклонен: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен недействителен или истек")

    if payload.get("type") != "access":
        logger.warning("[WARN] токен неверного типа: type=%r", payload.get("type"))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ожидался access token")

    raw_user_id = payload.get("sub")
    try:
        user_id = int(raw_user_id)
        if user_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        logger.warning("[WARN] некорректный sub в токене: %r", raw_user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен")

    user = await UserDAO.find_by_id(session, user_id)
    if not user:
        logger.warning("[WARN] токен ссылается на несуществующего пользователя id=%d", user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    if user.is_active is False:
        logger.warning("[WARN] заблокированный пользователь id=%d пытается получить доступ", user_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Учетная запись заблокирована")

    return user


async def get_current_candidate_user(user: User = Depends(get_current_user)) -> User:
    if user.role in HR_ROLES or user.role == ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Функция доступна только соискателям"
        )
    return user


async def get_current_hr_user(user: User = Depends(get_current_user)) -> User:
    if user.role not in HR_ROLES and user.role != ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ разрешен только для работодателей и HR"
        )
    return user


async def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role != ADMIN_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ только для администратора")
    return user
