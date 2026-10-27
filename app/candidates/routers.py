import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.dao import ApplicationDAO, CandidateDAO
from app.candidates.schemas import (
    SApplicationCreate, SApplicationOut, SInviteRequest, SResumeCreate, SResumeOut,
)
from app.config import settings
from app.database import get_async_session
from app.pagination import Page
from app.security.dependencies import get_current_candidate_user, get_current_hr_user
from app.users.models import User
from app.validation import ADMIN_ROLE
from app.vacancies.dao import VacancyDAO

router = APIRouter(prefix="/candidates", tags=["Candidates"])
logger = logging.getLogger("gribhh.candidates")


@router.get("/my-resumes", response_model=List[SResumeOut])
@router.get("/my-resumes/", response_model=List[SResumeOut])
async def get_my_resumes(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_candidate_user)
):
    return await CandidateDAO.get_user_resumes(session, user.id)


@router.get("/applications", response_model=Page[SApplicationOut])
async def get_my_applications(
        page: int = Query(1, ge=1),
        page_size: int = Query(6, ge=1, le=50),
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(get_current_candidate_user)
):
    return await ApplicationDAO.paginate_user_applications(
        session, user.id, page, page_size
    )


@router.post("/resumes", status_code=status.HTTP_201_CREATED, response_model=SResumeOut)
@router.post("/resumes/", status_code=status.HTTP_201_CREATED, response_model=SResumeOut)
async def create_resume(
    resume_data: SResumeCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_candidate_user)
):
    data = resume_data.model_dump()
    # Незаполненные контакты берутся из профиля пользователя
    if not data.get("full_name"):
        data["full_name"] = user.full_name or user.email
    if not data.get("email"):
        data["email"] = user.email

    try:
        resume = await CandidateDAO.add(session, **data, user_id=user.id)
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("[ERROR] create_resume: user_id=%d data=%r", user.id, data)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось сохранить резюме. Попробуйте позже."
        )
    return resume


@router.post("/apply", status_code=status.HTTP_201_CREATED)
@router.post("/apply/", status_code=status.HTTP_201_CREATED)
async def apply_for_vacancy(
    application_data: SApplicationCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_candidate_user)
):
    resume = await CandidateDAO.find_by_id(session, application_data.resume_id)
    if not resume or resume.user_id != user.id:
        # Одинаковый ответ, чтобы нельзя было перебором узнать чужие резюме
        logger.warning("[WARN] apply: user_id=%d указал чужое/несуществующее resume_id=%d",
                       user.id, application_data.resume_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Резюме не найдено")

    vacancy = await VacancyDAO.find_by_id(session, application_data.vacancy_id)
    if not vacancy:
        logger.warning("[WARN] apply: vacancy_id=%d не найдена", application_data.vacancy_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")
    if vacancy.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вакансия находится в архиве")

    if await ApplicationDAO.find_existing(session, vacancy.id, resume.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Вы уже откликались на эту вакансию с этим резюме")

    try:
        application = await ApplicationDAO.add(
            session,
            vacancy_id=vacancy.id,
            resume_id=resume.id,
            cover_letter=application_data.cover_letter,
            user_id=user.id
        )
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("[ERROR] apply: user_id=%d vacancy_id=%d resume_id=%d",
                         user.id, vacancy.id, resume.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось отправить отклик. Попробуйте позже."
        )
    return {"message": "Отклик отправлен", "application_id": application.id}


def build_invite_message(application, invite_text: str) -> MIMEMultipart:
    candidate = application.resume
    vacancy = application.vacancy
    employer = vacancy.user
    employer_name = (employer.full_name if employer else None) or "Отдел кадров"
    employer_email = employer.email if employer else settings.MAIL_FROM

    msg = MIMEMultipart()
    msg["Subject"] = f"Приглашение на собеседование: {vacancy.title} | GRIBHH"
    msg["From"] = settings.MAIL_FROM
    msg["To"] = candidate.email
    if employer:
        msg["Reply-To"] = employer_email

    body = f"""Здравствуйте, {candidate.full_name or 'кандидат'}!

{invite_text}

Ваш отклик на вакансию "{vacancy.title}" заинтересовал работодателя.

ДЕТАЛИ ВАКАНСИИ:
Должность: {vacancy.title}
Описание: {vacancy.description or 'уточняйте у работодателя'}
Зарплата: {vacancy.salary_from or 'не указана'} - {vacancy.salary_to or 'не указана'} ₽
Требуемый опыт: {vacancy.required_experience or 0} лет

РАБОТОДАТЕЛЬ:
Имя: {employer_name}
Email: {employer_email}

Свяжитесь с работодателем для согласования даты и времени собеседования
или ответьте на это письмо.

---
Сообщение отправлено через портал GRIBHH.
Если вы не откликались на эту вакансию, проигнорируйте это письмо.
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))
    return msg


@router.post("/applications/{application_id}/invite", status_code=status.HTTP_200_OK)
async def invite_candidate(
        invite_data: SInviteRequest,
        application_id: int = Path(gt=0),
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(get_current_hr_user)
):
    application = await ApplicationDAO.find_with_details(session, application_id)
    if not application:
        logger.warning("[WARN] invite: application_id=%d не найден", application_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")

    vacancy = application.vacancy
    if user.role != ADMIN_ROLE and vacancy.user_id != user.id:
        logger.warning("[WARN] invite: user_id=%d пытается пригласить на чужую вакансию id=%d",
                       user.id, vacancy.id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это отклик на чужую вакансию")

    if application.status == "invited":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Кандидат уже приглашен")

    if not application.resume or not application.resume.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У кандидата не указан email в резюме")

    msg = build_invite_message(application, invite_data.message)
    logger.info("invite: отправка письма на %s (application_id=%d) через %s:%d",
                msg["To"], application_id, settings.MAIL_SERVER, settings.MAIL_PORT)
    try:
        with smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=15) as server:
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        logger.error("[ERROR] invite: SMTP отклонил логин %r", settings.MAIL_USERNAME)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Ошибка аутентификации на почтовом сервере")
    except (smtplib.SMTPException, OSError) as e:
        logger.error("[ERROR] invite: письмо на %s не отправлено: %s: %s", msg["To"], type(e).__name__, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Не удалось отправить письмо кандидату")

    # Статус меняется только после успешной отправки письма,
    # иначе кандидат числился бы приглашенным, не получив приглашения
    application.status = "invited"
    await session.commit()

    return {
        "message": "Приглашение успешно отправлено",
        "status": "invited",
        "employer": (vacancy.user.full_name if vacancy.user else None) or "Отдел кадров",
        "employer_email": vacancy.user.email if vacancy.user else settings.MAIL_FROM
    }
