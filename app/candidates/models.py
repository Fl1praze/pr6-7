from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String)
    age = Column(Integer)
    gender = Column(String)
    target_position = Column(String, nullable=False)
    experience_years = Column(Integer, default=0)
    expected_salary = Column(Numeric(10, 2))
    skills = Column(String, nullable=False)
    employment_type = Column(String)

    # Привязка резюме к пользователю
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="candidates")
    applications = relationship("Application", back_populates="resume", cascade="all, delete-orphan")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    vacancy_id = Column(Integer, ForeignKey("vacancies.id"), nullable=False)
    resume_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    cover_letter = Column(String, nullable=True)
    status = Column(String, default="applied")
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    vacancy = relationship("Vacancy", back_populates="applications")
    resume = relationship("Candidate", back_populates="applications")