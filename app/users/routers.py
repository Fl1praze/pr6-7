import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.security.auth import (
    ACCESS_TOKEN_COOKIE, ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token, get_password_hash, login_limiter, verify_password,
)
from app.security.dependencies import get_current_admin_user, get_current_user
from app.users.dao import UserDAO
from app.users.models import User
from app.users.schemas import SUserLogin, SUserOut, SUserRegister, SUserRoleUpdate

router = APIRouter(prefix="/auth", tags=["Авторизация и пользователи"])
logger = logging.getLogger("gribhh.auth")


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


@router.post("/register", response_model=SUserOut, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: SUserRegister, session: AsyncSession = Depends(get_async_session)):
    existing_user = await UserDAO.find_by_email(session, user_data.email)
    if existing_user:
        logger.warning("[WARN] register: email=%r уже зарегистрирован", user_data.email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пользователь с таким email уже существует")

    try:
        new_user = await UserDAO.add(
            session,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
            is_active=True,
        )
        await session.commit()
    except IntegrityError:
        # Два одновременных запроса с одним email: проверка выше прошла у обоих
        await session.rollback()
        logger.warning("[WARN] register: гонка при регистрации email=%r", user_data.email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пользователь с таким email уже существует")

    logger.info("register: создан пользователь id=%d role=%r", new_user.id, new_user.role)
    return new_user


@router.post("/login")
async def login_user(
        user_data: SUserLogin,
        request: Request,
        response: Response,
        session: AsyncSession = Depends(get_async_session)
):
    client_ip = request.client.host if request.client else "unknown"
    limiter_key = f"{client_ip}:{user_data.email}"
    if login_limiter.is_blocked(limiter_key):
        logger.warning("[WARN] login: превышен лимит попыток ip=%s email=%r", client_ip, user_data.email)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много неудачных попыток входа. Повторите через минуту."
        )

    user = await UserDAO.find_by_email(session, user_data.email)
    if not user or not verify_password(user_data.password, user.hashed_password):
        login_limiter.register_failure(limiter_key)
        logger.warning("[WARN] login: неверные учетные данные email=%r ip=%s", user_data.email, client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")

    if user.is_active is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Учетная запись заблокирована")

    login_limiter.reset(limiter_key)
    access_token = create_access_token({"sub": str(user.id)})
    set_auth_cookie(response, access_token)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "full_name": user.full_name or user.email,
        "email": user.email
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role
    }


@router.patch("/change-role")
async def update_user_role(
    role_data: SUserRoleUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin_user)
):
    if role_data.user_id == current_user.id:
        # Иначе последний администратор может случайно лишить себя прав
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя изменить собственную роль")

    target_user = await UserDAO.find_by_id(session, role_data.user_id)
    if not target_user:
        logger.warning("[WARN] change-role: пользователь id=%d не найден", role_data.user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    target_user.role = role_data.new_role
    await session.commit()
    return {"message": f"Роль пользователя {target_user.email} успешно изменена на '{role_data.new_role}'"}


@router.post("/logout")
async def logout_user(response: Response):
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/", httponly=True, samesite="lax")
    return {"message": "Пользователь успешно вышел из системы"}
