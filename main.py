# main.py
import logging
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Импорты моделей для SQLAlchemy
import app.users.models
import app.candidates.models
import app.vacancies.models

from app.candidates.routers import router as candidates_router
from app.vacancies.routers import router as vacancies_router
from app.users.routers import router as users_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("gribhh")

app = FastAPI(title="HH Platform")

# Определяем абсолютный путь к папке static в корне проекта
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Раздаем статические файлы (JS, CSS, картинки)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Подключаем роутеры API
app.include_router(users_router)
app.include_router(candidates_router)
app.include_router(vacancies_router)

FIELD_NAMES = {
    "email": "Email", "password": "Пароль", "full_name": "ФИО", "role": "Роль",
    "phone": "Телефон", "age": "Возраст", "gender": "Пол",
    "target_position": "Желаемая должность", "experience_years": "Опыт работы",
    "expected_salary": "Зарплатные ожидания", "skills": "Навыки",
    "employment_type": "Тип занятости", "title": "Заголовок", "description": "Описание",
    "salary_from": "Зарплата от", "salary_to": "Зарплата до",
    "required_experience": "Требуемый опыт", "cover_letter": "Сопроводительное письмо",
    "vacancy_id": "Вакансия", "resume_id": "Резюме", "user_id": "Пользователь",
    "new_role": "Роль", "message": "Сообщение",
}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Ошибки ввода возвращаются одной понятной строкой с указанием поля."""
    messages = []
    for err in exc.errors():
        field = next((str(p) for p in reversed(err.get("loc", ())) if isinstance(p, str) and p != "body"), None)
        text = err.get("msg", "некорректное значение").removeprefix("Value error, ")
        messages.append(f"{FIELD_NAMES.get(field, field)}: {text}" if field else text)
    logger.warning("[WARN] %s %s: ошибка ввода %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "; ".join(messages), "errors": jsonable_errors(exc)},
    )


def jsonable_errors(exc: RequestValidationError) -> list:
    return [{"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]


# Главная страница с отдачей HTML-интерфейса
@app.get("/", include_in_schema=False)
async def root():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return JSONResponse(status_code=404, content={"detail": "index.html не найден в директории static"})
