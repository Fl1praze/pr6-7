"""Общие правила проверки входных данных (по образцу NewFastAPI/app/users/schemas.py)."""
import re
from typing import Annotated, Optional

from pydantic import AfterValidator, BeforeValidator, Field

NAME_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+(?:[ '\-][A-Za-zА-Яа-яЁё]+)*")
PHONE_RE = re.compile(r"\+?[0-9 ()\-]{6,20}")

MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128
MAX_NAME_LEN = 150
MIN_AGE, MAX_AGE = 14, 100
MAX_EXPERIENCE = 60
MAX_SALARY = 10_000_000

# Роли пользователей. "applicant" — устаревшее значение, которое раньше
# записывал /auth/register; оно обрабатывается так же, как "candidate".
CANDIDATE_ROLES = ("candidate", "applicant")
HR_ROLES = ("hr", "employer")
ADMIN_ROLE = "admin"
ALL_ROLES = ("candidate", "hr", "employer", "admin")
SELF_REGISTER_ROLES = ("candidate", "hr")

GENDERS = ("Мужской", "Женский")
EMPLOYMENT_TYPES = ("full_time", "part_time", "remote", "project", "internship")


def validate_person_name(v: str) -> str:
    v = " ".join(v.split())
    if not v:
        raise ValueError("ФИО не может быть пустым")
    if len(v) > MAX_NAME_LEN:
        raise ValueError(f"ФИО не может быть длиннее {MAX_NAME_LEN} символов")
    if any(ch.isdigit() for ch in v):
        raise ValueError("ФИО не должно содержать цифры")
    if not NAME_RE.fullmatch(v):
        raise ValueError("ФИО может содержать только буквы, пробел, дефис и апостроф")
    return v


def validate_password(v: str) -> str:
    message = (f"Пароль должен содержать от {MIN_PASSWORD_LEN} до {MAX_PASSWORD_LEN} символов, "
               "заглавную букву и цифру")
    if not MIN_PASSWORD_LEN <= len(v) <= MAX_PASSWORD_LEN:
        raise ValueError(message)
    if not any(ch.isupper() for ch in v):
        raise ValueError(message)
    if not any(ch.isdigit() for ch in v):
        raise ValueError(message)
    if v != v.strip():
        raise ValueError("Пароль не должен начинаться или заканчиваться пробелом")
    return v


def validate_phone(v: str) -> str:
    v = v.strip()
    if not PHONE_RE.fullmatch(v) or sum(ch.isdigit() for ch in v) < 6:
        raise ValueError("Телефон: 6–20 символов, только цифры, пробел, +, -, ( )")
    return v


def lower_email(v):
    return v.strip().lower() if isinstance(v, str) else v


def blank_to_none(v):
    """Пустая строка из HTML-формы означает «не заполнено», а не значение ''."""
    if isinstance(v, str) and not v.strip():
        return None
    return v


PersonName = Annotated[str, AfterValidator(validate_person_name)]
OptionalPersonName = Annotated[Optional[PersonName], BeforeValidator(blank_to_none)]
StrongPassword = Annotated[str, AfterValidator(validate_password)]
Phone = Annotated[Optional[str], BeforeValidator(blank_to_none),
                  AfterValidator(lambda v: validate_phone(v) if v is not None else v)]


def optional_int(ge: int, le: int):
    """Необязательное целое в диапазоне [ge, le]; пустая строка формы — None."""
    return Annotated[Optional[Annotated[int, Field(ge=ge, le=le)]], BeforeValidator(blank_to_none)]


def optional_float(ge: float, le: float):
    """Необязательное число в диапазоне [ge, le]; NaN и Inf отклоняются."""
    return Annotated[Optional[Annotated[float, Field(ge=ge, le=le, allow_inf_nan=False)]],
                     BeforeValidator(blank_to_none)]


def optional_text(max_length: int):
    return Annotated[Optional[Annotated[str, Field(max_length=max_length)]], BeforeValidator(blank_to_none)]


def required_text(min_length: int, max_length: int):
    """Обязательная строка: пробелы по краям удаляются до проверки длины."""
    return Annotated[str, BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v),
                     Field(min_length=min_length, max_length=max_length)]
