# filters.py
from typing import Union

from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from db.models import Session, Manager
from config import ADMIN_IDS


class IsAdminOrManager(Filter):
    async def __call__(self, message: Union[Message, CallbackQuery]) -> bool:
        user_id = message.from_user.id

        # Проверяем, является ли пользователь админом
        if user_id in ADMIN_IDS:
            return True

        # Проверяем, является ли пользователь менеджером
        async with Session() as session:
            result = await session.execute(
                select(Manager).where(Manager.manager_id == user_id)
            )
            manager = result.scalar_one_or_none()

            return manager is not None