import math

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select, desc

from bot import bot
from db.models import Session, User, Question, Event, Review
from config import ADMIN_IDS, STRINGS_PER_PAGE
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import datetime

from filters import IsAdminOrManager
from keyboard import get_main_keyboard, admin_keyboard, manager_keyboard

router = Router()


class AnswerState(StatesGroup):
    waiting_for_answer = State()


class EventState(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_date = State()
    waiting_for_video = State()


class EditEventState(StatesGroup):
    waiting_for_edit_choice = State()
    waiting_for_new_title = State()
    waiting_for_new_description = State()
    waiting_for_new_date = State()
    waiting_for_new_video = State()


async def get_all_users_unblock() -> list:
    """
    Возвращает множество ID пользователей с активными подписками.

    Включает только пользователей, которые не заблокировали бота
    (хотя бы одна подписка активна).

    Возвращает:
        Set[int]: Множество уникальных user_id
    """
    async with Session() as db:
        result = await db.execute(
            select(User.user_id).where(
                User.user_is_block == False
            )
        )
        # Преобразование результата в множество уникальных ID
    return [user for user in result.scalars()]


@router.message(Command("start"), IsAdminOrManager())
async def cmd_start_admin(message: Message):
    """Обработчик команды /start для администратора"""
    if message.from_user.id in ADMIN_IDS:
        keyboard = admin_keyboard
        role_text = "Администратор"
    else:
        keyboard = manager_keyboard
        role_text = "Менеджер"

    await message.answer(
        f"👨‍💼 Панель {role_text}\n✨ Добро пожаловать в систему управления!",
        reply_markup=keyboard
    )


@router.message(F.text == "📊 Главное меню", IsAdminOrManager())
async def main_menu_admin(message: Message):
    """Обработчик команды /start для администратора"""
    if message.from_user.id in ADMIN_IDS:
        keyboard = admin_keyboard
        role_text = "Администратор"
    else:
        keyboard = manager_keyboard
        role_text = "Менеджер"

    await message.answer(
        f"👨‍💼 Панель {role_text}\n✨ Добро пожаловать в систему управления!",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "admin_main", IsAdminOrManager())
async def admin_main_menu(callback: CallbackQuery):
    """Возврат в главное меню администратора"""
    if callback.from_user.id in ADMIN_IDS:
        keyboard = admin_keyboard
        role_text = "Администратор"
    else:
        keyboard = manager_keyboard
        role_text = "Менеджер"

    await callback.message.edit_text(
        f"👨‍💼 Панель {role_text}\n✨ Добро пожаловать в систему управления!",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "admin_questions", IsAdminOrManager())
async def admin_questions_menu(callback: CallbackQuery):
    """Меню вопросов для администратора"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Ожидают ответа", callback_data="view_unanswered:1")],
            [InlineKeyboardButton(text="✅ Отвеченные", callback_data="view_answered:1")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="admin_main")]
        ]
    )

    await callback.message.edit_text(
        "❓ Раздел вопросов пользователей",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_unanswered:"), IsAdminOrManager())
async def view_unanswered_questions(callback: CallbackQuery):
    """Просмотр неотвеченных вопросов с пагинацией"""
    page = int(callback.data.split(":")[1])

    async with Session() as session:
        # Получаем неотвеченные вопросы с информацией о пользователе
        query = (select(Question)
                 .where(Question.answer == None)
                 .order_by(desc(Question.created_at))
                 .offset((page - 1) * STRINGS_PER_PAGE)
                 .limit(STRINGS_PER_PAGE))

        result = await session.execute(query)
        questions = result.scalars().all()

        # Для каждого вопроса получаем информацию о пользователе отдельно
        questions_with_users = []
        for question in questions:
            user_query = select(User).where(User.user_id == question.user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            questions_with_users.append((question, user))

        # Получаем общее количество для пагинации
        count_query = select(Question).where(Question.answer == None)
        count_result = await session.execute(count_query)
        total_questions = len(count_result.scalars().all())

    total_pages = math.ceil(total_questions / STRINGS_PER_PAGE)

    # Создаем клавиатуру с вопросами
    keyboard_buttons = []
    for question, user in questions_with_users:
        date_str = question.created_at.strftime("%d.%m.%y")

        # Определяем имя пользователя
        if user:
            username = user.username if user.username else (
                user.first_name if user.first_name else (
                    user.last_name if user.last_name else f"ID{user.user_id}"
            ))
        else:
            # Если пользователь не найден, используем ID из вопроса
            username = f"ID{question.user_id}"

        button_text = f"{date_str} {username}"

        # Обрезаем текст если слишком длинный
        if len(button_text) > 30:
            button_text = button_text[:27] + "..."

        keyboard_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"question_detail:{question.id}"
        )])

    # Добавляем кнопки пагинации
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"view_unanswered:{page - 1}"
        ))

    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"view_unanswered:{page + 1}"
        ))

    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    # Добавляем кнопки навигации
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_questions")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        f"📋 Вопросы, ожидающие ответа (Страница {page}/{total_pages}):",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_answered:"), IsAdminOrManager())
async def view_answered_questions(callback: CallbackQuery):
    """Просмотр отвеченных вопросов с пагинацией"""
    page = int(callback.data.split(":")[1])

    async with Session() as session:
        # Получаем отвеченные вопросы
        query = (select(Question)
                 .where(Question.answer != None)
                 .order_by(desc(Question.answered_at))
                 .offset((page - 1) * STRINGS_PER_PAGE)
                 .limit(STRINGS_PER_PAGE))

        result = await session.execute(query)
        questions = result.scalars().all()

        # Для каждого вопроса получаем информацию о пользователе отдельно
        questions_with_users = []
        for question in questions:
            user_query = select(User).where(User.user_id == question.user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            questions_with_users.append((question, user))

        # Получаем общее количество для пагинации
        count_query = select(Question).where(Question.answer != None)
        count_result = await session.execute(count_query)
        total_questions = len(count_result.scalars().all())

    total_pages = math.ceil(total_questions / STRINGS_PER_PAGE)

    # Создаем клавиатуру с вопросами
    keyboard_buttons = []
    for question, user in questions_with_users:
        date_str = question.answered_at.strftime("%d.%m.%y") if question.answered_at else "??.??.??"

        # Определяем имя пользователя
        if user:
            username = user.username if user.username else (
                user.first_name if user.first_name else f"ID{user.user_id}"
            )
        else:
            # Если пользователь не найден, используем ID из вопроса
            username = f"ID{question.user_id}"

        button_text = f"{date_str} {username}"

        # Обрезаем текст если слишком длинный
        if len(button_text) > 30:
            button_text = button_text[:27] + "..."

        keyboard_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"question_detail:{question.id}"
        )])

    # Добавляем кнопки пагинации
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"view_answered:{page - 1}"
        ))

    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"view_answered:{page + 1}"
        ))

    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    # Добавляем кнопки навигации
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_questions")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        f"✅ Отвеченные вопросы (Страница {page}/{total_pages}):",
        reply_markup=keyboard
    )
    await callback.answer()


# Добавьте этот обработчик после существующих обработчиков
@router.callback_query(F.data.startswith("question_detail:"), IsAdminOrManager())
async def question_detail(callback: CallbackQuery, state: FSMContext):
    """Детальный просмотр вопроса"""
    question_id = int(callback.data.split(":")[1])

    async with Session() as session:
        # Получаем вопрос с информацией о пользователе
        question_query = select(Question).where(Question.id == question_id)
        stmt = await session.execute(question_query)
        question = stmt.scalar_one_or_none()
        user_query = select(User).where(User.user_id == question.user_id)
        stmt = await session.execute(user_query)
        user = stmt.scalar_one_or_none()

        if not question:
            await callback.answer("❌ Вопрос не найден")
            return

        # Формируем текст сообщения
        date_str = question.created_at.strftime("%d.%m.%Y %H:%M")

        if user:
            user_info = user.username if user.username else f"ID{user.user_id}"
        else:
            user_info = f"ID{question.user_id}"

        text = f"👤 Вопрос от пользователя: {user_info}\n"
        text += f"🕐 Дата обращения: {date_str}\n"
        text += f"❓ Текст вопроса: {question.question}"

        # Создаем клавиатуру
        keyboard_buttons = []

        if question.answer is None:
            # Если вопрос не отвечен - показываем кнопку "Ответить"
            keyboard_buttons.append([
                InlineKeyboardButton(text="💬 Ответить на вопрос", callback_data=f"answer_question:{question_id}")
            ])
        else:
            # Если вопрос отвечен - показываем ответ
            answer_date = question.answered_at.strftime("%d.%m.%Y %H:%M") if question.answered_at else "неизвестно"
            text += f"\n\n💬 Ответ: {question.answer}\n"
            text += f"✅ Ответ предоставлен: {answer_date}"

        keyboard_buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="view_unanswered:1")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()


@router.callback_query(F.data.startswith("answer_question:"), IsAdminOrManager())
async def start_answer(callback: CallbackQuery, state: FSMContext):
    """Начало процесса ответа на вопрос"""
    question_id = int(callback.data.split(":")[1])

    # Сохраняем ID вопроса в состоянии
    await state.set_state(AnswerState.waiting_for_answer)
    await state.update_data(question_id=question_id)

    await callback.message.edit_text("💬 Пожалуйста, введите ответ на вопрос пользователя:")
    await callback.answer()


@router.message(AnswerState.waiting_for_answer, IsAdminOrManager())
async def process_answer(message: Message, state: FSMContext):
    """Обработка ответа на вопрос"""
    data = await state.get_data()
    question_id = data['question_id']

    async with Session() as session:
        # Получаем вопрос и пользователя
        question_query = select(Question).where(Question.id == question_id)
        stmt = await session.execute(question_query)
        question = stmt.scalar_one_or_none()
        user_query = select(User).where(User.user_id == question.user_id)
        stmt = await session.execute(user_query)
        user = stmt.scalar_one_or_none()

        if question:
            # Обновляем вопрос
            question.answer = message.text
            question.answered_at = datetime.datetime.now()
            await session.commit()

            # Отправляем ответ пользователю
            try:
                await message.bot.send_message(
                    chat_id=question.user_id,
                    text=f"❓ Ваш вопрос: {question.question}\n\n💬 Ответ администратора: {message.text}\n\n✨ Благодарим за обращение!",
                    reply_markup = get_main_keyboard()
                )
            except Exception as e:
                print(f"❌ Ошибка при отправке сообщения пользователю: {e}")

            # Возвращаемся к списку неотвеченных вопросов
            await view_unanswered_questions_internal(message, state, page=1)
        else:
            await message.answer("❌ Вопрос не найден")

    await state.clear()


# Вспомогательная функция для отображения неотвеченных вопросов
async def view_unanswered_questions_internal(message: Message, state: FSMContext, page: int):
    """Внутренняя функция для отображения неотвеченных вопросов"""
    # Код аналогичный функции view_unanswered_questions, но адаптированный для вызова из других обработчиков
    async with Session() as session:
        query = (select(Question)
                 .where(Question.answer == None)
                 .order_by(desc(Question.created_at))
                 .offset((page - 1) * STRINGS_PER_PAGE)
                 .limit(STRINGS_PER_PAGE))

        result = await session.execute(query)
        questions = result.scalars().all()

        questions_with_users = []
        for question in questions:
            user_query = select(User).where(User.user_id == question.user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            questions_with_users.append((question, user))

        count_query = select(Question).where(Question.answer == None)
        count_result = await session.execute(count_query)
        total_questions = len(count_result.scalars().all())

    total_pages = math.ceil(total_questions / STRINGS_PER_PAGE)

    keyboard_buttons = []
    for question, user in questions_with_users:
        date_str = question.created_at.strftime("%d.%m.%y")

        if user:
            username = user.username if user.username else (
                user.first_name if user.first_name else (
                    user.last_name if user.last_name else f"ID{user.user_id}"
                ))
        else:
            username = f"ID{question.user_id}"

        button_text = f"{date_str} {username}"

        if len(button_text) > 30:
            button_text = button_text[:27] + "..."

        keyboard_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"question_detail:{question.id}"
        )])

    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"view_unanswered:{page - 1}"
        ))

    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"view_unanswered:{page + 1}"
        ))

    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_questions")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(
        f"📋 Вопросы, которые требуют ответа (Страница {page}/{total_pages}):",
        reply_markup=keyboard
    )


# Добавить обработчики после существующих
@router.callback_query(F.data == "admin_events", IsAdminOrManager())
async def admin_events_menu(callback: CallbackQuery):
    """Меню мероприятий для администратора"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Создать мероприятие", callback_data="create_event")],
            [InlineKeyboardButton(text="📋 Список мероприятий", callback_data="events_list")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")]
        ]
    )

    await callback.message.edit_text(
        "📅 Управление мероприятиями",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "create_event", IsAdminOrManager())
async def start_create_event(callback: CallbackQuery, state: FSMContext):
    """Начало создания мероприятия"""
    await callback.message.edit_text("📝 Введите название мероприятия:")
    await state.set_state(EventState.waiting_for_title)
    await callback.answer()


@router.message(EventState.waiting_for_title, IsAdminOrManager())
async def process_event_title(message: Message, state: FSMContext):
    """Обработка названия мероприятия"""
    await state.update_data(title=message.text)
    await message.answer("📄 Введите описание мероприятия:")
    await state.set_state(EventState.waiting_for_description)


@router.message(EventState.waiting_for_description, IsAdminOrManager())
async def process_event_description(message: Message, state: FSMContext):
    """Обработка описания мероприятия"""
    await state.update_data(description=message.text)
    await message.answer("📅 Введите дату мероприятия в формате ДД.ММ.ГГ (например, 25.12.24):")
    await state.set_state(EventState.waiting_for_date)


@router.message(EventState.waiting_for_date, IsAdminOrManager())
async def process_event_date(message: Message, state: FSMContext):
    """Обработка даты мероприятия с валидацией"""
    try:
        # Пытаемся распарсить дату из сообщения
        event_date = datetime.datetime.strptime(message.text, "%d.%m.%y")

        await state.update_data(event_date=event_date)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Нет видео", callback_data="no_video")]
            ]
        )

        await message.answer(
            "🎥 Введите ссылку на видео по мероприятию:",
            reply_markup=keyboard
        )
        await state.set_state(EventState.waiting_for_video)
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГ(например, 25.12.24):")


@router.callback_query(F.data == "no_video", EventState.waiting_for_video, IsAdminOrManager())
async def process_no_video(callback: CallbackQuery, state: FSMContext):
    """Обработка отсутствия видео"""
    await process_event_final(callback.message, state, None)
    await callback.answer()


@router.message(EventState.waiting_for_video, IsAdminOrManager())
async def process_event_video(message: Message, state: FSMContext):
    """Обработка ссылки на видео"""
    await process_event_final(message, state, message.text)


async def process_event_final(message: Message, state: FSMContext, video_url: str = None):
    """Финальная обработка и сохранение мероприятия"""
    data = await state.get_data()

    async with Session() as session:
        event = Event(
            title=data['title'],
            description=data['description'],
            event_date=data['event_date'],
            video_url=video_url,
            created_at=datetime.datetime.now()
        )
        session.add(event)
        await session.commit()
        event_id = event.id

    await message.answer("✅ Мероприятие успешно создано!")
    if video_url:
        users = await get_all_users_unblock()
        print(users)
        count = 0
        date_str = event.event_date.strftime("%d.%m.%Y")
        text = f"🎉 Новое мероприятие!\n\n<i>Название:</i> <b>{data['title']}</b>\n"
        text += f"<i>Дата проведения:</i> {date_str}\n\n"
        text += f"{data['description']}"
        text += f"\n\n<i>Ссылка на видео:</i> {video_url}\n\n"
        text += '💬 Поделитесь, пожалуйста, вашим мнением о мероприятии 👇'
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💬 Оставить отзыв", callback_data=f"leave_review:{event_id}")]
            ]
        )
        for user_id in users:
            try:
                await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode="HTML")
                count += 1
            except:
                pass
        await message.answer(f"✅ Уведомление о новом мероприятии отправлено {count} пользователям")


    # Возвращаем в меню мероприятий
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Создать мероприятие", callback_data="create_event")],
            [InlineKeyboardButton(text="📋 Мероприятия", callback_data="events_list")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")]
        ]
    )

    await message.answer("📅 Управление мероприятиями", reply_markup=keyboard)
    await state.clear()


# Замените существующие функции на эти:

@router.callback_query(F.data == "events_list", IsAdminOrManager())
async def show_events_list(callback: CallbackQuery):
    """Показ списка мероприятий с пагинацией"""
    await _show_events_page(callback, page=1)


@router.callback_query(F.data.startswith("events_page:"), IsAdminOrManager())
async def view_events_page(callback: CallbackQuery):
    """Просмотр страницы с мероприятиями"""
    page = int(callback.data.split(":")[1])
    await _show_events_page(callback, page)


async def _show_events_page(callback: CallbackQuery, page: int):
    """Внутренняя функция для отображения страницы с мероприятиями"""
    async with Session() as session:
        # Получаем мероприятия с сортировкой по дате
        query = (select(Event)
                 .order_by(desc(Event.event_date))
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
            callback_data=f"event_detail:{event.id}"  # Изменено с event_stub на event_detail
        )])

    # Добавляем кнопки пагинации
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"events_page:{page - 1}"
        ))

    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"events_page:{page + 1}"
        ))

    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    # Добавляем кнопку возврата
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_events")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        f"📅 Список мероприятий (Страница {page}/{total_pages}):",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("event_detail:"), IsAdminOrManager())
async def event_detail(callback: CallbackQuery):
    """Детальный просмотр мероприятия"""
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
        text += f"\n\n🎥 <i>Ссылка на видео:</i> {event.video_url if event.video_url else 'запись появится позже'}"

    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_event:{event_id}"),
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_event:{event_id}")
            ],
            [
                InlineKeyboardButton(text="📝 Отзывы", callback_data=f"reviews_list:{event_id}")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="events_list")
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# Обработчик удаления мероприятия
@router.callback_query(F.data.startswith("delete_event:"), IsAdminOrManager())
async def delete_event(callback: CallbackQuery):
    """Удаление мероприятия"""
    event_id = int(callback.data.split(":")[1])

    async with Session() as session:
        # Получаем мероприятие вместе с отзывами
        event_query = select(Event).where(Event.id == event_id)
        result = await session.execute(event_query)
        event = result.scalar_one_or_none()

        if event:
            # Удаляем мероприятие (отзывы удалятся каскадно благодаря настройкам в моделях)
            await session.delete(event)
            await session.commit()
            await callback.answer("✅ Мероприятие удалено")
        else:
            await callback.answer("❌ Мероприятие не найдено")

    # Отправляем новое сообщение со списком мероприятий
    await callback.message.answer("✅ Мероприятие удалено. Возвращаемся к списку мероприятий:")
    await _show_events_page_internal(callback.message, page=1)


# Добавляем вспомогательную функцию для показа страницы мероприятий
async def _show_events_page_internal(message: Message, page: int):
    """Внутренняя функция для отображения страницы с мероприятиями"""
    async with Session() as session:
        # Получаем мероприятия с сортировкой по дате
        query = (select(Event)
                 .order_by(desc(Event.event_date))
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
            callback_data=f"event_detail:{event.id}"
        )])

    # Добавляем кнопки пагинации
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"events_page:{page - 1}"
        ))

    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"events_page:{page + 1}"
        ))

    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    # Добавляем кнопку возврата
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_events")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(
        f"📅 Список мероприятий (Страница {page}/{total_pages}):",
        reply_markup=keyboard
    )


# Обработчик начала редактирования мероприятия
@router.callback_query(F.data.startswith("edit_event:"), IsAdminOrManager())
async def start_edit_event(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования мероприятия"""
    event_id = int(callback.data.split(":")[1])

    # Сохраняем ID мероприятия в состоянии
    await state.set_state(EditEventState.waiting_for_edit_choice)
    await state.update_data(event_id=event_id)

    # Показываем клавиатуру выбора поля для редактирования
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Название", callback_data="edit_field:title")],
            [InlineKeyboardButton(text="📄 Описание", callback_data="edit_field:description")],
            [InlineKeyboardButton(text="📅 Дата", callback_data="edit_field:date")],
            [InlineKeyboardButton(text="🎥 Видео", callback_data="edit_field:video")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"event_detail:{event_id}")]
        ]
    )

    await callback.message.edit_text("✏️ Выберите поле для редактирования:", reply_markup=keyboard)
    await callback.answer()


# Обработчик выбора поля для редактирования
@router.callback_query(F.data.startswith("edit_field:"), EditEventState.waiting_for_edit_choice, IsAdminOrManager())
async def select_edit_field(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора поля для редактирования"""
    field = callback.data.split(":")[1]
    data = await state.get_data()
    event_id = data['event_id']

    await state.update_data(edit_field=field)

    field_names = {
        "title": "название",
        "description": "описание",
        "date": "дату",
        "video": "ссылку на видео"
    }

    if field == "date":
        await callback.message.answer(f"📅 Введите новую {field_names[field]} в формате ДД.ММ.ГГ (например, 25.12.24):")
        await state.set_state(EditEventState.waiting_for_new_date)
    elif field == "video":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🗑️ Удалить видео", callback_data="remove_video")]
            ]
        )
        await callback.message.answer(
            f"🎥 Введите новую {field_names[field]} или нажмите кнопку чтобы удалить текущее:",
            reply_markup=keyboard
        )
        await state.set_state(EditEventState.waiting_for_new_video)
    else:
        await callback.message.answer(f"✏️ Введите новое {field_names[field]}:")
        await state.set_state(getattr(EditEventState, f"waiting_for_new_{field}"))

    await callback.answer()


# Обработчики для каждого типа поля
@router.message(EditEventState.waiting_for_new_title, IsAdminOrManager())
async def process_new_title(message: Message, state: FSMContext):
    """Обработка нового названия"""
    await update_event_field(message, state, "title", message.text)


@router.message(EditEventState.waiting_for_new_description, IsAdminOrManager())
async def process_new_description(message: Message, state: FSMContext):
    """Обработка нового описания"""
    await update_event_field(message, state, "description", message.text)


@router.message(EditEventState.waiting_for_new_date, IsAdminOrManager())
async def process_new_date(message: Message, state: FSMContext):
    """Обработка новой даты"""
    try:
        # Парсим дату
        event_date = datetime.datetime.strptime(message.text, "%d.%m.%y")
        await update_event_field(message, state, "event_date", event_date)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГ (например, 25.12.24):")


@router.message(EditEventState.waiting_for_new_video, IsAdminOrManager())
async def process_new_video(message: Message, state: FSMContext):
    """Обработка новой ссылки на видео"""
    await update_event_field(message, state, "video_url", message.text)
    data = await state.get_data()
    event_id = data['event_id']

    async with Session() as session:
        event_query = select(Event).where(Event.id == event_id)
        result = await session.execute(event_query)
        event = result.scalar_one_or_none()
    if event:
        users = await get_all_users_unblock()
        print(users)
        count = 0
        date_str = event.event_date.strftime("%d.%m.%Y")
        text = f"🎉 Новое мероприятие!\n\n<i>Название:</i> <b>{data['title']}</b>\n"
        text += f"<i>Дата проведения:</i> {date_str}\n\n"
        text += f"{data['description']}"
        text += f"\n\n<i>Ссылка на видео:</i> {event.video_url}\n\n"
        text += '💬 Поделитесь, пожалуйста, вашим мнением о мероприятии 👇'
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💬 Оставить отзыв", callback_data=f"leave_review:{event_id}")]
            ]
        )
        for user_id in users:
            try:
                await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode="HTML")
                count += 1
            except:
                pass
        await message.answer(f"✅ Уведомление о новом мероприятии отправлено {count} пользователям")


@router.callback_query(F.data == "remove_video", EditEventState.waiting_for_new_video, IsAdminOrManager())
async def process_remove_video(callback: CallbackQuery, state: FSMContext):
    """Удаление видео"""

    # Создаем временное сообщение для передачи в update_event_field
    class TempMessage:
        def __init__(self, callback):
            self.message_id = callback.message.message_id
            self.chat = callback.message.chat
            self.answer = callback.message.answer
            self.bot = callback.bot

    temp_message = TempMessage(callback)
    await update_event_field(temp_message, state, "video_url", None)
    await callback.answer()


# Общая функция для обновления поля мероприятия
async def update_event_field(message: Message, state: FSMContext, field: str, value: str):
    """Обновление поля мероприятия в БД"""
    data = await state.get_data()
    event_id = data['event_id']

    async with Session() as session:
        event_query = select(Event).where(Event.id == event_id)
        result = await session.execute(event_query)
        event = result.scalar_one_or_none()

        if event:
            setattr(event, field, value)
            await session.commit()
            await message.answer("✅ Изменения сохранены")

            # Отправляем новое сообщение с обновленными деталями
            await send_event_detail(message, event_id)
        else:
            await message.answer("❌ Мероприятие не найдено")

    await state.clear()


# Добавляем новую функцию для отправки деталей мероприятия
async def send_event_detail(message: Message, event_id: int):
    """Отправка деталей мероприятия в новом сообщении"""
    async with Session() as session:
        event_query = select(Event).where(Event.id == event_id)
        result = await session.execute(event_query)
        event = result.scalar_one_or_none()

        if not event:
            await message.answer("❌ Мероприятие не найдено")
            return

        # Форматируем дату
        date_str = event.event_date.strftime("%d.%m.%Y")

        # Формируем текст сообщения
        text = f"📌 <b>{event.title}</b>\n"
        text += f"📅 <i>Дата проведения: {date_str}</i>\n\n"
        text += f"📄 {event.description}"

        if event.video_url:
            text += f"\n\n🎥 <b>Видео:</b> {event.video_url}"

    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_event:{event_id}"),
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_event:{event_id}")
            ],
            [
                InlineKeyboardButton(text="📝 Отзывы", callback_data=f"reviews_list:{event_id}")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="events_list")
            ]
        ]
    )

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("reviews_list:"), IsAdminOrManager())
async def show_reviews_list(callback: CallbackQuery):
    """Показ списка отзывов для мероприятия"""
    event_id = int(callback.data.split(":")[1])
    await _show_reviews_page(callback, event_id, page=1)


@router.callback_query(F.data.startswith("reviews_page:"), IsAdminOrManager())
async def show_reviews_page(callback: CallbackQuery):
    """Просмотр страницы с отзывами"""
    data = callback.data.split(":")
    event_id = int(data[1])
    page = int(data[2])
    await _show_reviews_page(callback, event_id, page)


async def _show_reviews_page(callback: CallbackQuery, event_id: int, page: int):
    """Внутренняя функция для отображения страницы с отзывами"""
    async with Session() as session:
        # Получаем информацию о мероприятии
        event_query = select(Event).where(Event.id == event_id)
        event_result = await session.execute(event_query)
        event = event_result.scalar_one_or_none()

        if not event:
            await callback.answer("❌ Мероприятие не найдено")
            return

        # Получаем отзывы для этого мероприятия с пагинацией
        reviews_query = (select(Review)
                         .where(Review.event_id == event_id)
                         .order_by(desc(Review.created_at))
                         .offset((page - 1) * STRINGS_PER_PAGE)
                         .limit(STRINGS_PER_PAGE))
        reviews_result = await session.execute(reviews_query)
        reviews = reviews_result.scalars().all()

        # Для каждого отзыва получаем информацию о пользователе
        reviews_with_users = []
        for review in reviews:
            user_query = select(User).where(User.user_id == review.user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            reviews_with_users.append((review, user))

        # Получаем общее количество отзывов
        count_query = select(Review).where(Review.event_id == event_id)
        count_result = await session.execute(count_query)
        total_reviews = len(count_result.scalars().all())

    total_pages = math.ceil(total_reviews / STRINGS_PER_PAGE)

    # Формируем текст сообщения
    event_date_str = event.event_date.strftime("%d.%m.%Y")
    text = (f"📅 Мероприятие: {event.title}\n"
            f"📆 Дата проведения: {event_date_str}\n"
            f"💬 Все отзывы: {total_reviews}")

    # Создаем клавиатуру с отзывами
    keyboard_buttons = []
    for review, user in reviews_with_users:
        # Формируем текст кнопки: дата и информация о пользователе
        review_date = review.created_at.strftime("%d.%m.%y")

        if user:
            user_info = user.username if user.username else (
                user.first_name if user.first_name else f"ID{user.user_id}"
            )
        else:
            user_info = f"ID{review.user_id}"

        button_text = f"{review_date} {user_info}"

        # Обрезаем текст если слишком длинный
        if len(button_text) > 30:
            button_text = button_text[:27] + "..."

        keyboard_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"review_detail:{review.id}"
        )])

    # Добавляем кнопки пагинации
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"reviews_page:{event_id}:{page - 1}"
        ))
    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"reviews_page:{event_id}:{page + 1}"
        ))

    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    # Добавляем кнопку "Назад"
    keyboard_buttons.append([InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data=f"event_detail:{event_id}"
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("review_detail:"), IsAdminOrManager())
async def show_review_detail(callback: CallbackQuery):
    """Просмотр деталей отзыва"""
    review_id = int(callback.data.split(":")[1])

    async with Session() as session:
        # Получаем отзыв с информацией о пользователе и мероприятии
        review_query = select(Review).where(Review.id == review_id)
        review_result = await session.execute(review_query)
        review = review_result.scalar_one_or_none()

        if not review:
            await callback.answer("❌ Отзыв не найден")
            return

        # Получаем информацию о пользователе
        user_query = select(User).where(User.user_id == review.user_id)
        user_result = await session.execute(user_query)
        user = user_result.scalar_one_or_none()

        # Получаем информацию о мероприятии
        event_query = select(Event).where(Event.id == review.event_id)
        event_result = await session.execute(event_query)
        event = event_result.scalar_one_or_none()

    # Формируем текст сообщения
    if user:
        user_info = f"@{user.username}" if user.username else (
            user.first_name if user.first_name else f"ID{user.user_id}"
        )
    else:
        user_info = f"ID{review.user_id}"

    text = (f"👤 Пользователь: {user_info}\n"
            f"🆔 ID: {review.user_id}\n\n"
            f"💬 Отзыв:\n{review.text}")

    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"reviews_list:{review.event_id}"
            )]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
