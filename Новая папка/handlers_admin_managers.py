# handlers_admin_managers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from db.models import Session, Manager
from config import ADMIN_IDS
from keyboard import admin_keyboard

router = Router()


class ManagerState(StatesGroup):
    waiting_for_manager_id = State()
    waiting_for_delete_manager_id = State()


@router.callback_query(F.data == "admin_managers", F.from_user.id.in_(ADMIN_IDS))
async def admin_managers_menu(callback: CallbackQuery):
    """Меню управления менеджерами"""
    async with Session() as session:
        result = await session.execute(select(Manager))
        managers = result.scalars().all()

    manager_list = "\n".join(
        [f"• ID: {manager.manager_id}" for manager in managers]) if managers else "❌ Менеджеры отсутствуют"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить менеджера", callback_data="add_manager")],
            [InlineKeyboardButton(text="🗑️ Удалить менеджера", callback_data="delete_manager")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="admin_main")]
        ]
    )

    await callback.message.edit_text(
        f"👥 Управление менеджерами\n\n"
        f"📋 Текущие менеджеры:\n{manager_list}",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "add_manager", F.from_user.id.in_(ADMIN_IDS))
async def start_add_manager(callback: CallbackQuery, state: FSMContext):
    """Начало добавления менеджера"""
    await callback.message.edit_text(
        "👤 Введите Telegram ID пользователя, которого хотите добавить как менеджера:"
    )
    await state.set_state(ManagerState.waiting_for_manager_id)
    await callback.answer()


@router.message(ManagerState.waiting_for_manager_id, F.from_user.id.in_(ADMIN_IDS))
async def process_add_manager(message: Message, state: FSMContext):
    """Обработка добавления менеджера"""
    try:
        manager_id = int(message.text)

        async with Session() as session:
            # Проверяем, существует ли уже такой менеджер
            existing_manager = await session.execute(
                select(Manager).where(Manager.manager_id == manager_id)
            )
            if existing_manager.scalar_one_or_none():
                await message.answer("❌ Этот пользователь уже является менеджером!")
                return

            # Добавляем нового менеджера
            manager = Manager(manager_id=manager_id)
            session.add(manager)
            await session.commit()

        await message.answer("✅ Менеджер успешно добавлен!")
        await admin_managers_menu_internal(message)

    except ValueError:
        await message.answer("❌ Неверный формат ID! Пожалуйста, введите числовой Telegram ID.")

    await state.clear()


@router.callback_query(F.data == "delete_manager", F.from_user.id.in_(ADMIN_IDS))
async def start_delete_manager(callback: CallbackQuery, state: FSMContext):
    """Начало удаления менеджера"""
    async with Session() as session:
        result = await session.execute(select(Manager))
        managers = result.scalars().all()

    if not managers:
        await callback.answer("❌ Нет менеджеров для удаления!")
        return

    keyboard_buttons = []
    for manager in managers:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"🗑️ Удалить менеджера ID: {manager.manager_id}",
                callback_data=f"confirm_delete_manager:{manager.manager_id}"
            )
        ])

    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_managers")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        "🗑️ Выберите менеджера для удаления:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_manager:"), F.from_user.id.in_(ADMIN_IDS))
async def process_delete_manager(callback: CallbackQuery):
    """Подтверждение и удаление менеджера"""
    manager_id = int(callback.data.split(":")[1])

    async with Session() as session:
        manager = await session.execute(
            select(Manager).where(Manager.manager_id == manager_id)
        )
        manager = manager.scalar_one_or_none()

        if manager:
            await session.delete(manager)
            await session.commit()
            await callback.answer("✅ Менеджер успешно удален!")
        else:
            await callback.answer("❌ Менеджер не найден!")

    await admin_managers_menu_internal(callback.message)


async def admin_managers_menu_internal(message: Message):
    """Внутренняя функция для отображения меню менеджеров"""
    async with Session() as session:
        result = await session.execute(select(Manager))
        managers = result.scalars().all()

    manager_list = "\n".join(
        [f"• ID: {manager.manager_id}" for manager in managers]) if managers else "❌ Менеджеры отсутствуют"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить менеджера", callback_data="add_manager")],
            [InlineKeyboardButton(text="🗑️ Удалить менеджера", callback_data="delete_manager")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="admin_main")]
        ]
    )

    await message.answer(
        f"👥 Управление менеджерами\n\n"
        f"📋 Текущие менеджеры:\n{manager_list}",
        reply_markup=keyboard
    )