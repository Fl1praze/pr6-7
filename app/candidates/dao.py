# app/candidates/dao.py
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.candidates.models import Candidate, Application
from app.pagination import Page, clamp_page
from app.vacancies.models import Vacancy


class CandidateDAO(BaseDAO):
    model = Candidate

    @classmethod
    async def get_user_resumes(cls, session: AsyncSession, user_id: int) -> List[Candidate]:
        """Получить все резюме конкретного пользователя."""
        query = select(cls.model).filter_by(user_id=user_id)
        result = await session.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def add(cls, session: AsyncSession, **data) -> Candidate:
        """Создать новое резюме с фильтрацией лишних полей.

        Фиксация транзакции выполняется в роутере, чтобы при ошибке можно было
        откатить все изменения целиком.
        """
        valid_fields = {k: v for k, v in data.items() if hasattr(cls.model, k)}
        instance = cls.model(**valid_fields)
        session.add(instance)
        await session.flush()
        await session.refresh(instance)
        return instance


class ApplicationDAO(BaseDAO):
    model = Application

    @classmethod
    async def add(cls, session: AsyncSession, **data) -> Application:
        """Создать отклик на вакансию (без commit — см. CandidateDAO.add)."""
        valid_fields = {k: v for k, v in data.items() if hasattr(cls.model, k)}
        instance = cls.model(**valid_fields)
        session.add(instance)
        await session.flush()
        await session.refresh(instance)
        return instance

    @classmethod
    async def find_existing(cls, session: AsyncSession, vacancy_id: int, resume_id: int) -> Optional[Application]:
        """Проверка повторного отклика тем же резюме на ту же вакансию."""
        query = select(cls.model).filter_by(vacancy_id=vacancy_id, resume_id=resume_id)
        result = await session.execute(query)
        return result.scalars().first()

    @classmethod
    async def get_vacancy_applications(
        cls, session: AsyncSession, vacancy_id: int
    ) -> List[Application]:
        """Получить все отклики на конкретную вакансию."""
        query = select(cls.model).filter_by(vacancy_id=vacancy_id)
        result = await session.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def find_user_applications(cls, session: AsyncSession, user_id: int) -> List[Application]:
        """Возвращает все отклики конкретного соискателя вместе с данными вакансий."""
        query = (
            select(cls.model)
            .options(selectinload(cls.model.vacancy))
            .where(cls.model.user_id == user_id)
            .order_by(cls.model.created_at.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def paginate_user_applications(
        cls, session: AsyncSession, user_id: int, page: int, page_size: int
    ) -> Page:
        """Отклики соискателя постранично, вместе с данными вакансии."""
        total = await session.scalar(
            select(func.count(cls.model.id)).where(cls.model.user_id == user_id)
        ) or 0
        page = clamp_page(page, total, page_size)

        query = (
            select(cls.model)
            .options(selectinload(cls.model.vacancy))
            .where(cls.model.user_id == user_id)
            .order_by(cls.model.created_at.desc().nullslast(), cls.model.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list((await session.execute(query)).scalars().all())
        return Page.create(items, total, page, page_size)

    @classmethod
    async def paginate_for_vacancy(
        cls, session: AsyncSession, vacancy_id: int, page: int, page_size: int
    ) -> Page:
        """Отклики на конкретную вакансию постранично, вместе с резюме."""
        total = await session.scalar(
            select(func.count(cls.model.id)).where(cls.model.vacancy_id == vacancy_id)
        ) or 0
        page = clamp_page(page, total, page_size)

        query = (
            select(cls.model)
            .options(selectinload(cls.model.resume))
            .where(cls.model.vacancy_id == vacancy_id)
            .order_by(cls.model.created_at.desc().nullslast(), cls.model.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list((await session.execute(query)).scalars().all())
        return Page.create(items, total, page, page_size)

    @classmethod
    async def find_with_details(cls, session: AsyncSession, application_id: int) -> Optional[Application]:
        """Отклик вместе с резюме, вакансией и автором вакансии.

        Связь vacancy.user обязательно загружается заранее: ленивая загрузка
        в асинхронной сессии вызывает MissingGreenlet.
        """
        query = (
            select(cls.model)
            .options(
                selectinload(cls.model.resume),
                selectinload(cls.model.vacancy).selectinload(Vacancy.user),
            )
            .filter(cls.model.id == application_id)
        )
        result = await session.execute(query)
        return result.scalars().first()
