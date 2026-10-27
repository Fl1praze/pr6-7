import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.dao import ApplicationDAO
from app.database import get_async_session
from app.pagination import Page
from app.security.dependencies import get_current_admin_user, get_current_hr_user
from app.users.models import User
from app.validation import ADMIN_ROLE
from app.vacancies.dao import VacancyDAO
from app.vacancies.schemas import (
    SApplicationForVacancy,
    SVacancyCreate,
    SVacancyFilter,
    SVacancyForHR,
    SVacancyPublic,
)

router = APIRouter(prefix="/vacancies", tags=["Vacancies"])
logger = logging.getLogger("gribhh.vacancies")

VacancyStatus = Literal["active", "archived", "all"]


@router.get("/", response_model=Page[SVacancyPublic])
@router.get("", response_model=Page[SVacancyPublic])
async def get_all_vacancies(
        filters: SVacancyFilter = Depends(),
        session: AsyncSession = Depends(get_async_session)
):
    # Общий список доступен без авторизации, поэтому отклики (ФИО и email
    # кандидатов) в ответ не попадают. Архивные вакансии отсекаются в DAO.
    return await VacancyDAO.search_active(session, filters)


@router.get("/my", response_model=Page[SVacancyForHR])
async def get_my_vacancies(
        filters: SVacancyFilter = Depends(),
        vacancy_status: VacancyStatus = Query("active", alias="status"),
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(get_current_hr_user)
):
    return await VacancyDAO.search_for_hr(
        session,
        filters,
        user_id=user.id,
        is_admin=user.role == ADMIN_ROLE,
        status=vacancy_status,
    )


@router.get("/admin/all", response_model=Page[SVacancyForHR])
async def get_all_vacancies_for_admin(
        filters: SVacancyFilter = Depends(),
        vacancy_status: VacancyStatus = Query("all", alias="status"),
        session: AsyncSession = Depends(get_async_session),
        admin: User = Depends(get_current_admin_user)
):
    return await VacancyDAO.search_for_hr(
        session,
        filters,
        user_id=admin.id,
        is_admin=True,
        status=vacancy_status,
    )


@router.get("/{vacancy_id}/applications", response_model=Page[SApplicationForVacancy])
async def get_vacancy_applications(
        vacancy_id: int = Path(gt=0),
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=50),
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(get_current_hr_user)
):
    """Отклики на вакансию постранично — для кабинета HR."""
    vacancy = await VacancyDAO.find_by_id(session, vacancy_id)
    if not vacancy:
        logger.warning("[WARN] applications: vacancy_id=%d не найдена", vacancy_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")

    if user.role != ADMIN_ROLE and vacancy.user_id != user.id:
        logger.warning("[WARN] applications: user_id=%d запрашивает отклики чужой вакансии id=%d",
                       user.id, vacancy_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав на просмотр откликов этой вакансии"
        )

    return await ApplicationDAO.paginate_for_vacancy(session, vacancy_id, page, page_size)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=SVacancyPublic)
@router.post("", status_code=status.HTTP_201_CREATED, response_model=SVacancyPublic)
async def create_vacancy(
        vacancy_data: SVacancyCreate,
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(get_current_hr_user)
):
    vacancy = await VacancyDAO.add(session, **vacancy_data.model_dump(), user_id=user.id)
    await session.commit()
    return vacancy


@router.delete("/{vacancy_id}", status_code=status.HTTP_200_OK)
async def delete_or_archive_vacancy(
        vacancy_id: int = Path(gt=0),
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(get_current_hr_user)
):
    vacancy = await VacancyDAO.find_by_id(session, vacancy_id)
    if not vacancy:
        logger.warning("[WARN] archive: vacancy_id=%d не найдена (user_id=%d)", vacancy_id, user.id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")

    if user.role != ADMIN_ROLE and vacancy.user_id != user.id:
        logger.warning("[WARN] archive: user_id=%d пытается архивировать чужую вакансию id=%d",
                       user.id, vacancy_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав на удаление этой вакансии"
        )

    if vacancy.is_archived:
        return {"message": "Вакансия уже находится в архиве", "id": vacancy_id}

    vacancy.is_archived = True
    await session.commit()
    return {"message": "Вакансия перенесена в архив", "id": vacancy_id}
