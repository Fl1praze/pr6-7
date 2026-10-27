from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

class BaseDAO:
    model = None

    @classmethod
    async def find_by_id(cls, session: AsyncSession, model_id: int):
        query = select(cls.model).filter_by(id=model_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def find_all(cls, session: AsyncSession, **filter_by):
        query = select(cls.model).filter_by(**filter_by)
        result = await session.execute(query)
        return result.scalars().all()

    @classmethod
    async def add(cls, session: AsyncSession, **data):
        instance = cls.model(**data)
        session.add(instance)
        await session.flush()
        return instance

    @classmethod
    async def delete(cls, session: AsyncSession, model_id: int):
        instance = await cls.find_by_id(session, model_id)
        if instance:
            await session.delete(instance)
            await session.flush()
            return True
        return False