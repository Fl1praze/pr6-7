from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Vacancy(Base):
    __tablename__ = "vacancies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    salary_from = Column(Numeric(10, 2))
    salary_to = Column(Numeric(10, 2))
    required_experience = Column(Integer, default=0)
    is_archived = Column(Boolean, default=False)  # <-- Добавлено поле

    # Автор вакансии (HR)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Важно: имя связи 'user' соответствует back_populates в User
    user = relationship("User", back_populates="vacancies")

    # Связь с откликами
    applications = relationship(
        "Application", back_populates="vacancy", cascade="all, delete-orphan"
    )