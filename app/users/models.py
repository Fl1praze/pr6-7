from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="candidate")
    is_active = Column(Boolean, default=True)

    candidates = relationship("Candidate", back_populates="user", cascade="all, delete-orphan")
    vacancies = relationship("Vacancy", back_populates="user", cascade="all, delete-orphan")