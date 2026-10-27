from typing import Annotated, Literal, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

from app.validation import PersonName, StrongPassword, lower_email

NormalizedEmail = Annotated[EmailStr, BeforeValidator(lower_email)]


class SUserRegister(BaseModel):
    email: NormalizedEmail
    password: StrongPassword
    full_name: PersonName
    # Администратора можно назначить только через /auth/change-role
    role: Literal["candidate", "hr"] = "candidate"


class SUserLogin(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=128)


class SUserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    role: str

    model_config = ConfigDict(from_attributes=True)


class SUserRoleUpdate(BaseModel):
    user_id: int = Field(gt=0)
    new_role: Literal["candidate", "hr", "employer", "admin"]
