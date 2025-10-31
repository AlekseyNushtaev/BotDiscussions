# handlers_admin_poll.py
import datetime
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from db.models import Session, Poll, PollAnswer, PollMessage, PollVote
from filters import IsAdminOrManager
from keyboard import admin_keyboard, manager_keyboard
from config import ADMIN_IDS
from bot import bot
from handlers_admin import get_all_users_unblock
from handlers_user import get_all_admins_and_managers

router = Router()


class PollState(StatesGroup):
    waiting_for_poll_text = State()
    waiting_for_first_answer = State()
    waiting_for_second_answer = State()
    waiting_for_more_answers = State()
    waiting_for_confirmation = State()


@router.callback_query(F.data == "create_poll", IsAdminOrManager())
async def start_create_poll(callback: CallbackQuery, state: FSMContext):
    """Начало создания опроса"""
    await callback.message.answer("📊 Введите текст опроса:")
    await state.set_state(PollState.waiting_for_poll_text)
    await callback.answer()


@router.message(PollState.waiting_for_poll_text, IsAdminOrManager())
async def process_poll_text(message: Message, state: FSMContext):
    """Обработка текста опроса"""
    await state.update_data(poll_text=message.text)
    await message.answer("Назначьте текст первого варианта ответа:")
    await state.set_state(PollState.waiting_for_first_answer)


@router.message(PollState.waiting_for_first_answer, IsAdminOrManager())
async def process_first_answer(message: Message, state: FSMContext):
    """Обработка первого варианта ответа"""
    await state.update_data(first_answer=message.text)
    await message.answer("Назначьте текст второго варианта ответа:")
    await state.set_state(PollState.waiting_for_second_answer)


@router.message(PollState.waiting_for_second_answer, IsAdminOrManager())
async def process_second_answer(message: Message, state: FSMContext):
    """Обработка второго варианта ответа"""
    await state.update_data(second_answer=message.text)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="more_answers_yes"),
             InlineKeyboardButton(text="❌ Нет", callback_data="more_answers_no")]
        ]
    )
    await message.answer("Назначить еще один вариант ответа?", reply_markup=keyboard)
    await state.set_state(PollState.waiting_for_more_answers)


@router.callback_query(F.data.startswith("more_answers_"), PollState.waiting_for_more_answers, IsAdminOrManager())
async def process_more_answers(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора: добавлять еще ответы или нет"""
    if callback.data == "more_answers_yes":
        await callback.message.answer("Назначьте текст варианта ответа:")
        await state.set_state(PollState.waiting_for_more_answers)
    else:
        # Показываем итоговый опрос для подтверждения
        data = await state.get_data()
        poll_text = data['poll_text']
        answers = [data['first_answer'], data['second_answer']]

        # Добавляем дополнительные ответы, если они есть
        additional_answers = data.get('additional_answers', [])
        answers.extend(additional_answers)

        # Формируем сообщение для предварительного просмотра
        text = f"📊 Внимание опрос!!!\n\n{poll_text}\n\nВарианты ответов:\n"
        for i, answer in enumerate(answers, 1):
            text += f"{i}. {answer}\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Создать опрос", callback_data="confirm_poll_yes"),
                 InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_poll_no")]
            ]
        )
        await callback.message.answer(text)
        await callback.message.answer("Создать опрос?", reply_markup=keyboard)
        await state.set_state(PollState.waiting_for_confirmation)

    await callback.answer()


@router.message(PollState.waiting_for_more_answers, IsAdminOrManager())
async def process_additional_answer(message: Message, state: FSMContext):
    """Обработка дополнительных вариантов ответа"""
    data = await state.get_data()
    additional_answers = data.get('additional_answers', [])
    additional_answers.append(message.text)
    await state.update_data(additional_answers=additional_answers)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="more_answers_yes"),
             InlineKeyboardButton(text="❌ Нет", callback_data="more_answers_no")]
        ]
    )
    await message.answer("Назначить еще один вариант ответа?", reply_markup=keyboard)


@router.callback_query(F.data.startswith("confirm_poll_"), PollState.waiting_for_confirmation, IsAdminOrManager())
async def process_confirm_poll(callback: CallbackQuery, state: FSMContext):
    """Обработка подтверждения создания опроса"""
    if callback.data == "confirm_poll_yes":
        # Сохраняем опрос в базу данных
        data = await state.get_data()
        poll_text = data['poll_text']
        answers = [data['first_answer'], data['second_answer']]

        # Добавляем дополнительные ответы, если они есть
        additional_answers = data.get('additional_answers', [])
        answers.extend(additional_answers)

        async with Session() as session:
            # Создаем опрос
            poll = Poll(
                tg_id=callback.from_user.id,
                text_poll=poll_text,
                time_stamp=datetime.datetime.now()
            )
            session.add(poll)
            await session.commit()

            # Создаем варианты ответов
            for answer_text in answers:
                poll_answer = PollAnswer(
                    poll_id=poll.id,
                    text_answer=answer_text
                )
                session.add(poll_answer)

            await session.commit()

            # Рассылаем опрос
            await send_poll_to_all(poll.id)

            # Отправляем сообщение о успешном создании
            if callback.from_user.id in ADMIN_IDS:
                keyboard = admin_keyboard
            else:
                keyboard = manager_keyboard
            await callback.message.answer("✅ Опрос создан и разослан!", reply_markup=keyboard)
    else:
        # Отмена создания опроса
        if callback.from_user.id in ADMIN_IDS:
            keyboard = admin_keyboard
        else:
            keyboard = manager_keyboard
        await callback.message.answer("❌ Создание опроса отменено.", reply_markup=keyboard)

    await state.clear()
    await callback.answer()


async def send_poll_to_all(poll_id: int):
    """Рассылает опрос всем пользователям"""
    async with Session() as session:
        # Получаем опрос с вариантами ответов с помощью явного запроса
        from sqlalchemy.orm import selectinload

        poll_query = select(Poll).options(selectinload(Poll.answers)).where(Poll.id == poll_id)
        result = await session.execute(poll_query)
        poll = result.scalar_one_or_none()

        if not poll:
            return

        answers = poll.answers

    # Получаем список пользователей, которые уже проголосовали
    async with Session() as session:
        voted_users_query = select(PollVote.user_id).where(PollVote.poll_id == poll_id)
        voted_users_result = await session.execute(voted_users_query)
        voted_users = [user_id for (user_id,) in voted_users_result.all()]

    # Формируем текст опроса
    text = f"📊 Внимание опрос!!!\n\n{poll.text_poll}\n\n"

    # Проверяем, есть ли уже голоса
    total_votes = sum(answer.value for answer in answers)
    if total_votes > 0:
        text += "Текущие результаты:\n"
        for answer in answers:
            percentage = (answer.value / total_votes) * 100 if total_votes > 0 else 0
            text += f"• {answer.text_answer}: {answer.value} ({percentage:.1f}%)\n"
        text += "\n"

    # Создаем клавиатуру с вариантами ответов
    keyboard_buttons = []
    for answer in answers:
        keyboard_buttons.append([InlineKeyboardButton(
            text=answer.text_answer,
            callback_data=f"poll_vote:{poll_id}:{answer.id}"
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    # Получаем список всех пользователей (включая админов и менеджеров)
    users = await get_all_users_unblock()
    admins_managers = await get_all_admins_and_managers()
    all_users = list(set(users + admins_managers))  # Убираем дубликаты

    # Рассылаем опрос
    for user_id in all_users:
        try:
            # Проверяем, голосовал ли уже пользователь
            if user_id in voted_users:
                # Пользователь уже голосовал - отправляем без клавиатуры
                message = await bot.send_message(
                    user_id,
                    text
                )
            else:
                # Пользователь еще не голосовал - отправляем с клавиатурой
                message = await bot.send_message(
                    user_id,
                    text,
                    reply_markup=keyboard
                )

            # Сохраняем информацию о сообщении для возможности обновления
            async with Session() as session:
                poll_message = PollMessage(
                    poll_id=poll_id,
                    chat_id=user_id,
                    message_id=message.message_id
                )
                session.add(poll_message)
                await session.commit()
        except Exception as e:
            print(f"Не удалось отправить опрос пользователю {user_id}: {e}")


@router.callback_query(F.data.startswith("poll_vote:"))
async def process_poll_vote(callback: CallbackQuery):
    """Обработка голоса в опросе"""
    data = callback.data.split(":")
    poll_id = int(data[1])
    answer_id = int(data[2])

    async with Session() as session:
        # Проверяем, не голосовал ли уже пользователь
        existing_vote = await session.execute(
            select(PollVote).where(
                PollVote.poll_id == poll_id,
                PollVote.user_id == callback.from_user.id
            )
        )
        if existing_vote.scalar_one_or_none():
            await callback.answer("Вы уже голосовали в этом опросе!", show_alert=True)
            return

        # Увеличиваем счетчик выбранного варианта
        answer_query = select(PollAnswer).where(PollAnswer.id == answer_id)
        answer_result = await session.execute(answer_query)
        answer = answer_result.scalar_one_or_none()

        if answer:
            answer.value += 1

            # Сохраняем информацию о голосе
            poll_vote = PollVote(
                poll_id=poll_id,
                user_id=callback.from_user.id,
                answer_id=answer_id
            )
            session.add(poll_vote)
            await session.commit()

            # Получаем обновленные данные опроса с помощью selectinload
            from sqlalchemy.orm import selectinload

            poll_query = select(Poll).options(selectinload(Poll.answers)).where(Poll.id == poll_id)
            poll_result = await session.execute(poll_query)
            poll = poll_result.scalar_one_or_none()

            answers = poll.answers

            # Формируем обновленный текст опроса
            text = f"📊 Внимание опрос!!!\n\n{poll.text_poll}\n\n"
            total_votes = sum(answer.value for answer in answers)

            text += "Текущие результаты:\n"
            for ans in answers:
                percentage = (ans.value / total_votes) * 100 if total_votes > 0 else 0
                text += f"• {ans.text_answer}: {ans.value} ({percentage:.1f}%)\n"

            # Убираем клавиатуру у пользователя, который проголосовал
            await callback.message.edit_text(text, reply_markup=None)

            # Обновляем сообщения у всех пользователей
            messages_query = select(PollMessage).where(PollMessage.poll_id == poll_id)
            messages_result = await session.execute(messages_query)
            messages = messages_result.scalars().all()

            # Получаем список пользователей, которые уже проголосовали
            voted_users_query = select(PollVote.user_id).where(PollVote.poll_id == poll_id)
            voted_users_result = await session.execute(voted_users_query)
            voted_users = [user_id for (user_id,) in voted_users_result.all()]

            # Создаем клавиатуру для тех, кто еще не голосовал
            keyboard_buttons = []
            for ans in answers:
                keyboard_buttons.append([InlineKeyboardButton(
                    text=ans.text_answer,
                    callback_data=f"poll_vote:{poll_id}:{ans.id}"
                )])

            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

            for message in messages:
                # Пропускаем сообщение пользователя, который только что проголосовал
                if message.chat_id == callback.from_user.id:
                    continue

                # Проверяем, голосовал ли уже этот пользователь
                if message.chat_id in voted_users:
                    # У пользователя уже есть голос - убираем клавиатуру
                    try:
                        await bot.edit_message_text(
                            chat_id=message.chat_id,
                            message_id=message.message_id,
                            text=text,
                            reply_markup=None
                        )
                    except Exception as e:
                        # Если сообщение не найдено (пользователь удалил и т.д.), то пропускаем
                        pass
                else:
                    # Пользователь еще не голосовал - оставляем клавиатуру
                    try:
                        await bot.edit_message_text(
                            chat_id=message.chat_id,
                            message_id=message.message_id,
                            text=text,
                            reply_markup=keyboard
                        )
                    except Exception as e:
                        # Если сообщение не найдено (пользователь удалил и т.д.), то пропускаем
                        pass

    await callback.answer("Спасибо за ваш голос!")