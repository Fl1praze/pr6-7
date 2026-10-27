from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

from app.validation import (
    MAX_AGE, MAX_EXPERIENCE, MAX_SALARY, MIN_AGE, OptionalPersonName, Phone,
    blank_to_none, lower_email, optional_float, optional_int, optional_text, required_text,
)

OptionalEmail = Annotated[Optional[EmailStr], BeforeValidator(blank_to_none), BeforeValidator(lower_email)]


class SResumeCreate(BaseModel):
    full_name: OptionalPersonName = None
    email: OptionalEmail = None
    phone: Phone = None
    age: optional_int(MIN_AGE, MAX_AGE) = None
    gender: Annotated[Optional[Literal["Мужской", "Женский"]], BeforeValidator(blank_to_none)] = None
    target_position: required_text(2, 160)
    experience_years: optional_int(0, MAX_EXPERIENCE) = 0
    expected_salary: optional_float(0, MAX_SALARY) = None
    skills: required_text(2, 2000)
    employment_type: Annotated[
        Optional[Literal["full_time", "part_time", "remote", "project", "internship"]],
        BeforeValidator(blank_to_none)
    ] = None

    model_config = ConfigDict(from_attributes=True)


class SResumeOut(BaseModel):
    id: int
    user_id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    target_position: str
    experience_years: Optional[int] = 0
    expected_salary: Optional[float] = None
    skills: str
    employment_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SApplicationCreate(BaseModel):
    vacancy_id: int = Field(gt=0)
    resume_id: int = Field(gt=0)
    cover_letter: optional_text(3000) = None


class SInviteRequest(BaseModel):
    message: required_text(1, 2000) = "Вы приглашены на собеседование!"


class SVacancyForApplication(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    salary_from: Optional[float] = 0
    salary_to: Optional[float] = 0
    is_archived: Optional[bool] = False
    model_config = ConfigDict(from_attributes=True)


class SApplicationOut(BaseModel):
    id: int
    vacancy_id: int
    resume_id: int
    cover_letter: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    vacancy: Optional[SVacancyForApplication] = None

    model_config = ConfigDict(from_attributes=True)
