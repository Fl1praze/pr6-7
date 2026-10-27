from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.pagination import PageParams
from app.validation import MAX_EXPERIENCE, MAX_SALARY, optional_float, optional_int, optional_text, required_text


class SVacancyFilter(PageParams):
    """Параметры поиска вакансий.

    q ищет подстроку в заголовке и описании, остальные поля сужают выборку.
    page/page_size наследуются от PageParams.
    """
    q: optional_text(100) = None
    salary_from: optional_float(0, MAX_SALARY) = None
    salary_to: optional_float(0, MAX_SALARY) = None
    max_experience: optional_int(0, MAX_EXPERIENCE) = None
    sort: Literal["new", "salary_asc", "salary_desc"] = "new"

    @model_validator(mode="after")
    def check_salary_range(self):
        if self.salary_from and self.salary_to and self.salary_to < self.salary_from:
            raise ValueError(
                f"Зарплата «до» ({self.salary_to:g}) меньше зарплаты «от» ({self.salary_from:g})"
            )
        return self


class SResumeForApplication(BaseModel):
    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    target_position: str
    experience_years: Optional[int] = 0
    skills: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SApplicationForVacancy(BaseModel):
    id: int
    user_id: Optional[int] = None
    resume_id: Optional[int] = None
    cover_letter: Optional[str] = None
    status: str
    resume: Optional[SResumeForApplication] = None

    model_config = ConfigDict(from_attributes=True)


class SVacancyCreate(BaseModel):
    title: required_text(2, 200)
    description: optional_text(5000) = None
    salary_from: optional_float(0, MAX_SALARY) = 0
    salary_to: optional_float(0, MAX_SALARY) = 0
    required_experience: optional_int(0, MAX_EXPERIENCE) = 0

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def check_salary_range(self):
        # 0 или пустое значение означают «не указано»
        if self.salary_from and self.salary_to and self.salary_to < self.salary_from:
            raise ValueError(
                f"Зарплата «до» ({self.salary_to:g}) меньше зарплаты «от» ({self.salary_from:g})"
            )
        return self


class SVacancyPublic(BaseModel):
    """Вакансия для общего списка: без откликов и персональных данных кандидатов."""
    id: int
    title: str
    description: Optional[str] = None
    salary_from: Optional[float] = 0
    salary_to: Optional[float] = 0
    required_experience: Optional[int] = 0
    is_archived: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)


class SVacancyWithApplications(SVacancyPublic):
    applications: List[SApplicationForVacancy] = []


class SVacancyForHR(SVacancyPublic):
    """Вакансия в кабинете HR: без тяжёлой загрузки всех откликов."""
    applications_count: int = 0
