import datetime

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.models import Session, Question, User
from bot import bot
from config import ADMIN_IDS
from keyboard import get_main_keyboard

router = Router()


class QuestionState(StatesGroup):
    waiting_for_question = State()


@router.message(Command("start"), ~F.from_user.id.in_(ADMIN_IDS))
async def cmd_start(message: Message):
    async with Session() as session:
        # Проверяем существование пользователя
        user_query = select(User).where(User.user_id == message.from_user.id)
        result = await session.execute(user_query)
        user = result.scalar_one_or_none()

        if not user:

            user = User(
                user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                user_is_block=False
            )
            session.add(user)

        await session.commit()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Задать вопрос", callback_data="ask_question")],
            [InlineKeyboardButton(text="Календарь мероприятий", callback_data="events_calendar")]
        ]
    )

    await message.answer(
        "Добро пожаловать, задайте вопрос или выберите интересующее вас мероприятие.",
        reply_markup=keyboard
    )


@router.message(F.text == "📊 Главное меню", ~F.from_user.id.in_(ADMIN_IDS))
async def main_menu(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Задать вопрос", callback_data="ask_question")],
            [InlineKeyboardButton(text="Календарь мероприятий", callback_data="events_calendar")]
        ]
    )

    await message.answer(
        "Добро пожаловать, задайте вопрос или выберите интересующее вас мероприятие.",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "ask_question")
async def ask_question(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Задайте пжл свой вопрос")
    await state.set_state(QuestionState.waiting_for_question)
    await callback.answer()


@router.message(QuestionState.waiting_for_question)
async def receive_question(message: Message, state: FSMContext):
    # Сохраняем вопрос в базу данных
    async with Session() as session:
        question = Question(
            user_id=message.from_user.id,
            question=message.text,
            created_at=datetime.datetime.now()
        )
        session.add(question)
        await session.commit()

    # Отправляем подтверждение пользователю
    await message.answer("Ваш вопрос принят")

    # Пересылаем сообщение с вопросом администраторам
    for admin_id in ADMIN_IDS:
        try:
            # Пересылаем оригинальное сообщение
            await bot.send_message(
                admin_id,
                f"Вопрос от пользователя {message.from_user.full_name} (@{message.from_user.username} ID{message.from_user.id})", reply_markup=get_main_keyboard())
            await message.forward(admin_id)

        except Exception as e:
            print(f"Ошибка при отправке сообщения администратору {admin_id}: {e}")

    # Возвращаем главное меню
    await state.clear()
    await cmd_start(message)


import math
from sqlalchemy import select, desc
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Добавьте эти импорты в начало файла, если их нет
from db.models import Event
from config import STRINGS_PER_PAGE

# Добавьте этот обработчик после существующих обработчиков в handlers_user.py

@router.callback_query(F.data == "events_calendar")
async def show_user_events(callback: CallbackQuery):
    """Показ списка мероприятий для пользователя"""
    await _show_user_events_page(callback, page=1)


@router.callback_query(F.data.startswith("user_events_page:"))
async def view_user_events_page(callback: CallbackQuery):
    """Просмотр страницы с мероприятиями для пользователя"""
    page = int(callback.data.split(":")[1])
    await _show_user_events_page(callback, page)


async def _show_user_events_page(callback: CallbackQuery, page: int):
    """Внутренняя функция для отображения страницы с мероприятиями для пользователя"""
    async with Session() as session:
        # Получаем мероприятия с сортировкой по дате (ближайшие сначала)
        query = (select(Event)
                 .order_by(Event.event_date)
                 .offset((page - 1) * STRINGS_PER_PAGE)
                 .limit(STRINGS_PER_PAGE))

        result = await session.execute(query)
        events = result.scalars().all()

        # Получаем общее количество для пагинации
        count_query = select(Event)
        count_result = await session.execute(count_query)
        total_events = len(count_result.scalars().all())

    total_pages = math.ceil(total_events / STRINGS_PER_PAGE)

    # Создаем клавиатуру с мероприятиями
    keyboard_buttons = []
    for event in events:
        date_str = event.event_date.strftime("%d.%m.%y")
        button_text = f"{date_str} {event.title}"

        # Обрезаем текст если слишком длинный
        if len(button_text) > 30:
            button_text = button_text[:27] + "..."

        keyboard_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"user_event_detail:{event.id}"
        )])

    # Добавляем кнопки пагинации
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"user_events_page:{page - 1}"
        ))

    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"user_events_page:{page + 1}"
        ))

    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    # Добавляем кнопку возврата в главное меню
    keyboard_buttons.append([
        InlineKeyboardButton(text="📊 Главное меню", callback_data="user_main_menu")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        f"Календарь мероприятий (Страница {page}/{total_pages}):",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_event_detail:"))
async def user_event_detail(callback: CallbackQuery):
    """Детальный просмотр мероприятия для пользователя"""
    event_id = int(callback.data.split(":")[1])

    async with Session() as session:
        event_query = select(Event).where(Event.id == event_id)
        result = await session.execute(event_query)
        event = result.scalar_one_or_none()

        if not event:
            await callback.answer("Мероприятие не найдено")
            return

        # Форматируем дату
        date_str = event.event_date.strftime("%d.%m.%Y")

        # Формируем текст сообщения
        text = f"<i>Название:</i> <b>{event.title}</b>\n"
        text += f"<i>Дата проведения:</i> {date_str}\n\n"
        text += f"{event.description}"
        text += f"\n\n<i>Ссылка на видео:</i> {event.video_url if event.video_url else 'запись появится позже'}"


    # Создаем клавиатуру для пользователя
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Оставить отзыв", callback_data="review_stub")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="user_events_back")
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "review_stub")
async def review_stub(callback: CallbackQuery):
    """Заглушка для отзывов от пользователя"""
    await callback.answer("Функционал отзывов в разработке", show_alert=True)


@router.callback_query(F.data == "user_events_back")
async def user_events_back(callback: CallbackQuery):
    """Возврат к списку мероприятий для пользователя"""
    await _show_user_events_page(callback, page=1)


@router.callback_query(F.data == "user_main_menu")
async def user_main_menu(callback: CallbackQuery):
    """Возврат в главное меню пользователя"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Задать вопрос", callback_data="ask_question")],
            [InlineKeyboardButton(text="Календарь мероприятий", callback_data="events_calendar")]
        ]
    )

    await callback.message.edit_text(
        "Добро пожаловать, задайте вопрос или выберите интересующее вас мероприятие.",
        reply_markup=keyboard
    )
    await callback.answer()