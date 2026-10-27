from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dao.base import BaseDAO
from app.users.models import User

class UserDAO(BaseDAO):
    model = User

    @classmethod
    async def find_by_email(cls, session: AsyncSession, email: str):
        query = select(User).filter_by(email=email)
        result = await session.execute(query)
        return result.scalar_one_or_none()