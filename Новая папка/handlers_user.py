import datetime
import math
from sqlalchemy import select, desc
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated, FSInputFile

from db.models import Event, Manager
from config import STRINGS_PER_PAGE
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command, ChatMemberUpdatedFilter, KICKED, MEMBER
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.models import Session, Question, User, Event, Review
from bot import bot
from config import ADMIN_IDS
from keyboard import get_main_keyboard

router = Router()


class QuestionState(StatesGroup):
    waiting_for_question = State()


class ReviewState(StatesGroup):
    waiting_for_review = State()


async def get_all_admins_and_managers():
    """Возвращает список ID всех администраторов и менеджеров"""
    admins_and_managers = ADMIN_IDS.copy()  # Начинаем с администраторов

    # Добавляем менеджеров из базы данных
    async with Session() as session:
        result = await session.execute(select(Manager))
        managers = result.scalars().all()
        for manager in managers:
            admins_and_managers.append(manager.manager_id)

    return admins_and_managers


async def add_user(user_id, username, first_name, last_name):
    async with Session() as session:
        # Проверяем существование пользователя
        user_query = select(User).where(User.user_id == user_id)
        result = await session.execute(user_query)
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                user_is_block=False
            )
            session.add(user)

        await session.commit()


@router.message(Command("start"), ~F.from_user.id.in_(ADMIN_IDS))
async def cmd_start(message: Message):
    await add_user(message.from_user.id,
                   message.from_user.username,
                   message.from_user.first_name,
                   message.from_user.last_name)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ask_question")],
            [InlineKeyboardButton(text="📅 Календарь мероприятий", callback_data="events_calendar")]
        ]
    )

    await message.answer(
        "👋 Добро пожаловать!\n\n❓ Задайте вопрос или выберите интересующее вас мероприятие. 📅",
        reply_markup=keyboard
    )


@router.message(F.text == "📊 Главное меню", ~F.from_user.id.in_(ADMIN_IDS))
async def main_menu(message: Message):
    await add_user(message.from_user.id,
                   message.from_user.username,
                   message.from_user.first_name,
                   message.from_user.last_name)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ask_question")],
            [InlineKeyboardButton(text="📅 Календарь мероприятий", callback_data="events_calendar")]
        ]
    )

    await message.answer(
        "👋 Добро пожаловать!\n\n❓ Задайте вопрос или выберите интересующее вас мероприятие. 📅",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "ask_question")
async def ask_question(callback: CallbackQuery, state: FSMContext):
    await add_user(callback.from_user.id,
                   callback.from_user.username,
                   callback.from_user.first_name,
                   callback.from_user.last_name)
    await callback.message.answer_photo(photo=FSInputFile('vopros.jpg'),
                                        caption="❓ Пожалуйста, задайте ваш вопрос\.\n\n"
                                                "_Отправляя сообщение Вы соглашаетесь с [Политикой конфиденциальности](https://docs.google.com/document/d/10ehddmBkX9HeN0ycN4Wa8Xs6Ent1yL62HHO3rDR4lUs/edit?usp=sharing)_",
                                        parse_mode="MarkdownV2")
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
    await message.answer("✅ Ваш вопрос принят. Мы ответим вам в ближайшее время.")

    # Пересылаем сообщение с вопросом администраторам
    admins_and_managers = await get_all_admins_and_managers()
    for admin_id in admins_and_managers:
        try:
            # Пересылаем оригинальное сообщение
            await bot.send_message(
                admin_id,
                f"❓ Новый вопрос от пользователя {message.from_user.full_name} (@{message.from_user.username} ID{message.from_user.id})",
                reply_markup=get_main_keyboard())
            await message.forward(admin_id)

        except Exception as e:
            print(f"❌ Ошибка при отправке сообщения администратору {admin_id}: {e}")

    # Возвращаем главное меню
    await state.clear()
    await cmd_start(message)


@router.callback_query(F.data == "events_calendar")
async def show_user_events(callback: CallbackQuery):
    """Показ списка мероприятий для пользователя"""
    await add_user(callback.from_user.id,
                   callback.from_user.username,
                   callback.from_user.first_name,
                   callback.from_user.last_name)
    await _show_user_events_page(callback, page=1)


@router.callback_query(F.data.startswith("user_events_page:"))
async def view_user_events_page(callback: CallbackQuery):
    await add_user(callback.from_user.id,
                   callback.from_user.username,
                   callback.from_user.first_name,
                   callback.from_user.last_name)
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
            text="➡️ Вперед",
            callback_data=f"user_events_page:{page + 1}"
        ))

    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    # Добавляем кнопку возврата в главное меню
    keyboard_buttons.append([
        InlineKeyboardButton(text="📊 Главное меню", callback_data="user_main_menu")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.answer_photo(
        photo=FSInputFile('mero.jpg'),
        caption=f"📅 Календарь мероприятий 📋 (Страница {page}/{total_pages}):",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_event_detail:"))
async def user_event_detail(callback: CallbackQuery):
    """Детальный просмотр мероприятия для пользователя"""
    await add_user(callback.from_user.id,
                   callback.from_user.username,
                   callback.from_user.first_name,
                   callback.from_user.last_name)
    event_id = int(callback.data.split(":")[1])

    async with Session() as session:
        event_query = select(Event).where(Event.id == event_id)
        result = await session.execute(event_query)
        event = result.scalar_one_or_none()

        if not event:
            await callback.answer("❌ Мероприятие не найдено")
            return

        # Форматируем дату
        date_str = event.event_date.strftime("%d.%m.%Y")

        # Формируем текст сообщения
        text = f"📌 <i>Название:</i> <b>{event.title}</b>\n"
        text += f"📅 <i>Дата проведения:</i> {date_str}\n\n"
        text += f"📄 {event.description}"
        text += f"\n\n🎥 <i>Ссылка на видео:</i> {event.video_url if event.video_url else '📹 запись появится позже'}"

    # Создаем клавиатуру для пользователя
    keyboard_buttons = []

    # Проверяем, можно ли оставить отзыв (дата мероприятия <= текущей даты)
    if event.event_date.date() <= datetime.datetime.now().date():
        keyboard_buttons.append([
            InlineKeyboardButton(text="💬 Оставить отзыв", callback_data=f"leave_review:{event_id}")
        ])

    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад к мероприятиям", callback_data="user_events_back")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("leave_review:"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    """Начало процесса оставления отзыва"""
    await add_user(callback.from_user.id,
                   callback.from_user.username,
                   callback.from_user.first_name,
                   callback.from_user.last_name)
    event_id = int(callback.data.split(":")[1])

    # Сохраняем ID мероприятия в состоянии
    await state.set_state(ReviewState.waiting_for_review)
    await state.update_data(event_id=event_id)

    await callback.message.edit_text("💬 Пожалуйста, напишите ваш отзыв о мероприятии:")
    await callback.answer()


@router.message(ReviewState.waiting_for_review)
async def process_review(message: Message, state: FSMContext):
    """Обработка отзыва от пользователя"""
    data = await state.get_data()
    event_id = data['event_id']

    async with Session() as session:
        # Получаем информацию о мероприятии
        event_query = select(Event).where(Event.id == event_id)
        result = await session.execute(event_query)
        event = result.scalar_one_or_none()

        # Получаем информацию о пользователе
        user_query = select(User).where(User.user_id == message.from_user.id)
        user_result = await session.execute(user_query)
        user = user_result.scalar_one_or_none()

        if event and user:
            # Сохраняем отзыв в базу данных
            review = Review(
                user_id=message.from_user.id,
                event_id=event_id,
                text=message.text,
                created_at=datetime.datetime.now()
            )
            session.add(review)
            await session.commit()

            # Формируем информацию о пользователе
            user_info = user.username if user.username else f"ID{user.user_id}"

            # Отправляем уведомление администраторам
            admins_and_managers = await get_all_admins_and_managers()
            for admin_id in admins_and_managers:
                try:
                    # Отправляем информацию об отзыве
                    await bot.send_message(
                        admin_id,
                        f"💬 Новый отзыв от пользователя {user_info} по мероприятию:\n"
                        f"📌 Название: {event.title}\n"
                        f"📅 Дата проведения: {event.event_date.strftime('%d.%m.%Y')}"
                    )

                    # Пересылаем сообщение с отзывом
                    await message.forward(admin_id)

                except Exception as e:
                    print(f"❌ Ошибка при отправке отзыва администратору {admin_id}: {e}")

            # Благодарим пользователя и возвращаем в главное меню
            await message.answer("🙏 Благодарим за ваш отзыв! ✨")
            await cmd_start(message)
        else:
            await message.answer("❌ Ошибка при сохранении отзыва. Попробуйте позже.")

    await state.clear()


@router.callback_query(F.data == "user_events_back")
async def user_events_back(callback: CallbackQuery):
    """Возврат к списку мероприятий для пользователя"""
    await add_user(callback.from_user.id,
                   callback.from_user.username,
                   callback.from_user.first_name,
                   callback.from_user.last_name)
    await _show_user_events_page(callback, page=1)


@router.callback_query(F.data == "user_main_menu")
async def user_main_menu(callback: CallbackQuery):
    """Возврат в главное меню пользователя"""
    await add_user(callback.from_user.id,
                   callback.from_user.username,
                   callback.from_user.first_name,
                   callback.from_user.last_name)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ask_question")],
            [InlineKeyboardButton(text="📅 Календарь мероприятий", callback_data="events_calendar")]
        ]
    )

    await callback.message.answer(
        "👋 Добро пожаловать!\n\n❓ Задайте вопрос или выберите интересующее вас мероприятие. 📅",
        reply_markup=keyboard
    )
    await callback.answer()


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def user_blocked_bot(event: ChatMemberUpdated):
    await add_user(event.from_user.id,
                   event.from_user.username,
                   event.from_user.first_name,
                   event.from_user.last_name)
    async with Session() as session:
        stmt = select(User).where(User.user_id == event.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            user.user_is_block = True
            await session.commit()


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def user_unblocked_bot(event: ChatMemberUpdated):
    await add_user(event.from_user.id,
                   event.from_user.username,
                   event.from_user.first_name,
                   event.from_user.last_name)
    async with Session() as session:
        stmt = select(User).where(User.user_id == event.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            user.user_is_block = False
            await session.commit()
