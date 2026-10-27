"""Тесты защитных проверок входных данных (не требуют БД).

Запуск из корня проекта:  python -m pytest tests -v
"""
import os

import pytest
from pydantic import ValidationError

# Settings() читает .env при импорте; для тестов достаточно заглушек
for key, value in {
    "DB_HOST": "localhost", "DB_PORT": "5432", "DB_USER": "u", "DB_PASS": "p", "DB_NAME": "db",
    "SECRET_KEY": "x" * 40, "ALGORITHM": "HS256", "REDIS_HOST": "localhost", "REDIS_PORT": "6379",
    "MAIL_USERNAME": "m", "MAIL_PASSWORD": "m", "MAIL_FROM": "m@example.com",
    "MAIL_PORT": "465", "MAIL_SERVER": "smtp.example.com",
}.items():
    os.environ.setdefault(key, value)

from app.candidates.schemas import SApplicationCreate, SResumeCreate  # noqa: E402
from app.security.auth import LoginRateLimiter, verify_password  # noqa: E402
from app.users.schemas import SUserLogin, SUserRegister, SUserRoleUpdate  # noqa: E402
from app.vacancies.schemas import SVacancyCreate  # noqa: E402

VALID_USER = {"email": "User@Mail.ru", "password": "Secret123", "full_name": "Иванов Иван"}
VALID_RESUME = {"target_position": "Python-разработчик", "skills": "FastAPI, SQL"}


def test_register_valid_and_email_normalized():
    user = SUserRegister(**VALID_USER)
    assert user.email == "user@mail.ru"
    assert user.role == "candidate"


@pytest.mark.parametrize("password", ["1", "short1A", "alllowercase1", "NoDigitsHere", " Secret123"])
def test_register_rejects_weak_password(password):
    with pytest.raises(ValidationError):
        SUserRegister(**{**VALID_USER, "password": password})


@pytest.mark.parametrize("name", ["", "   ", "Иван2", "<script>", "Иван!!"])
def test_register_rejects_bad_full_name(name):
    with pytest.raises(ValidationError):
        SUserRegister(**{**VALID_USER, "full_name": name})


@pytest.mark.parametrize("role", ["admin", "root", ""])
def test_register_rejects_privileged_or_unknown_role(role):
    with pytest.raises(ValidationError):
        SUserRegister(**{**VALID_USER, "role": role})


def test_register_rejects_bad_email():
    with pytest.raises(ValidationError):
        SUserRegister(**{**VALID_USER, "email": "not-an-email"})


def test_login_rejects_empty_password():
    with pytest.raises(ValidationError):
        SUserLogin(email="a@b.ru", password="")


@pytest.mark.parametrize("data", [{"user_id": 0, "new_role": "hr"}, {"user_id": 1, "new_role": "superuser"}])
def test_role_update_rejects_bad_input(data):
    with pytest.raises(ValidationError):
        SUserRoleUpdate(**data)


@pytest.mark.parametrize("field,value", [
    ("age", 5), ("age", 999), ("experience_years", -1), ("experience_years", 1000),
    ("expected_salary", -1), ("expected_salary", float("nan")), ("expected_salary", float("inf")),
    ("email", "not-an-email"), ("phone", "abc"), ("gender", "XXX"), ("employment_type", "hack"),
    ("target_position", "   "), ("skills", ""),
])
def test_resume_rejects_bad_values(field, value):
    with pytest.raises(ValidationError):
        SResumeCreate(**{**VALID_RESUME, field: value})


def test_resume_blank_form_fields_become_none():
    resume = SResumeCreate(**VALID_RESUME, full_name="", email="", phone="", age="")
    assert resume.full_name is None and resume.email is None and resume.age is None
    assert resume.phone is None


def test_vacancy_salary_range():
    with pytest.raises(ValidationError):
        SVacancyCreate(title="Backend", salary_from=200000, salary_to=100000)
    assert SVacancyCreate(title="Backend", salary_from=100000, salary_to=0).salary_to == 0


@pytest.mark.parametrize("data", [{"title": "  "}, {"title": "QA", "salary_from": -5},
                                  {"title": "QA", "required_experience": 100}])
def test_vacancy_rejects_bad_values(data):
    with pytest.raises(ValidationError):
        SVacancyCreate(**data)


def test_application_ids_must_be_positive():
    with pytest.raises(ValidationError):
        SApplicationCreate(vacancy_id=0, resume_id=1)


def test_verify_password_survives_broken_hash():
    assert verify_password("Secret123", "not-a-hash") is False


def test_login_rate_limiter_blocks_after_limit():
    limiter = LoginRateLimiter(max_attempts=3, window_seconds=60)
    for _ in range(3):
        assert not limiter.is_blocked("ip:user")
        limiter.register_failure("ip:user")
    assert limiter.is_blocked("ip:user")
    limiter.reset("ip:user")
    assert not limiter.is_blocked("ip:user")
