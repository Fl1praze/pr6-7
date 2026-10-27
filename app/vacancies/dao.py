from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.models import Application
from app.dao.base import BaseDAO
from app.pagination import Page, clamp_page
from app.vacancies.models import Vacancy
from app.vacancies.schemas import SVacancyFilter

VacancyStatus = Literal["active", "archived", "all"]


def escape_like(value: str) -> str:
    """Экранирует % и _, чтобы пользователь не мог задать шаблон LIKE."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class VacancyDAO(BaseDAO):
    model = Vacancy

    @staticmethod
    def _filter_conditions(filters: SVacancyFilter) -> list:
        conditions = []

        query_text = (filters.q or "").strip()
        if query_text:
            pattern = f"%{escape_like(query_text)}%"
            conditions.append(
                or_(
                    Vacancy.title.ilike(pattern, escape="\\"),
                    Vacancy.description.ilike(pattern, escape="\\"),
                )
            )

        # Вакансия подходит, если её верхняя граница зарплаты не ниже запрошенной
        if filters.salary_from is not None:
            conditions.append(
                func.coalesce(Vacancy.salary_to, Vacancy.salary_from) >= filters.salary_from
            )

        # ... и нижняя граница не выше верхней границы фильтра
        if filters.salary_to is not None:
            conditions.append(
                func.coalesce(Vacancy.salary_from, Vacancy.salary_to) <= filters.salary_to
            )

        if filters.max_experience is not None:
            conditions.append(
                func.coalesce(Vacancy.required_experience, 0) <= filters.max_experience
            )

        return conditions

    @staticmethod
    def _order_by(sort: str) -> list:
        if sort == "salary_asc":
            return [
                func.coalesce(Vacancy.salary_from, Vacancy.salary_to).asc().nullslast(),
                Vacancy.id.desc(),
            ]
        if sort == "salary_desc":
            return [
                func.coalesce(Vacancy.salary_from, Vacancy.salary_to).desc().nullslast(),
                Vacancy.id.desc(),
            ]
        return [Vacancy.id.desc()]

    @classmethod
    async def _paginate(
        cls,
        session: AsyncSession,
        conditions: list,
        filters: SVacancyFilter,
        *,
        with_application_counts: bool = False,
    ) -> Page:
        total = await session.scalar(
            select(func.count(Vacancy.id)).where(*conditions)
        ) or 0
        page = clamp_page(filters.page, total, filters.page_size)
        offset = (page - 1) * filters.page_size

        if with_application_counts:
            query = (
                select(Vacancy, func.count(Application.id).label("applications_count"))
                .outerjoin(Application, Application.vacancy_id == Vacancy.id)
                .where(*conditions)
                .group_by(Vacancy.id)
                .order_by(*cls._order_by(filters.sort))
                .offset(offset)
                .limit(filters.page_size)
            )
            rows = (await session.execute(query)).all()
            items = []
            for vacancy, applications_count in rows:
                # Временный атрибут читает Pydantic-схема SVacancyForHR
                vacancy.applications_count = applications_count
                items.append(vacancy)
        else:
            query = (
                select(Vacancy)
                .where(*conditions)
                .order_by(*cls._order_by(filters.sort))
                .offset(offset)
                .limit(filters.page_size)
            )
            items = list((await session.execute(query)).scalars().all())

        return Page.create(items, total, page, filters.page_size)

    @classmethod
    async def search_active(
        cls, session: AsyncSession, filters: SVacancyFilter
    ) -> Page:
        """Публичный поиск: только неархивные вакансии."""
        conditions = [Vacancy.is_archived.isnot(True), *cls._filter_conditions(filters)]
        return await cls._paginate(session, conditions, filters)

    @classmethod
    async def search_for_hr(
        cls,
        session: AsyncSession,
        filters: SVacancyFilter,
        user_id: int,
        *,
        is_admin: bool = False,
        status: VacancyStatus = "active",
    ) -> Page:
        """Вакансии кабинета HR (или все вакансии для администратора)."""
        conditions = []

        if not is_admin:
            conditions.append(Vacancy.user_id == user_id)

        if status == "active":
            conditions.append(Vacancy.is_archived.isnot(True))
        elif status == "archived":
            conditions.append(Vacancy.is_archived.is_(True))
        elif status != "all":
            raise ValueError(f"Неизвестный статус вакансий: {status}")

        conditions.extend(cls._filter_conditions(filters))
        return await cls._paginate(
            session, conditions, filters, with_application_counts=True
        )
