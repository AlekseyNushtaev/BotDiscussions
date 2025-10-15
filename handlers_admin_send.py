import asyncio
from datetime import datetime

from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import bot

from aiogram import Router, types, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State, default_state
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from collections import defaultdict
from typing import Dict, List
from config import ADMIN_IDS
from db.models import Session, Post
from handlers_admin import get_all_users_unblock
from keyboard import create_kb, kb_button, admin_keyboard

router = Router()

media_groups: Dict[str, List[Message]] = defaultdict(list)
timers: Dict[str, asyncio.Task] = {}
builder = InlineKeyboardBuilder()

builder.row(InlineKeyboardButton(text="✅ Записаться на консультацию", callback_data="quest_1"))
builder.row(InlineKeyboardButton(text="📢 Подписаться на телеграм канал", url="https://t.me/andreikuvshinov"))

main_keyboard_markup = builder.as_markup()

class FSMFillForm(StatesGroup):
    send = State()
    text_add_button = State()
    check_text_1 = State()
    check_text_1_time = State()
    check_text_2 = State()
    check_text_2_time = State()
    text_add_button_text = State()
    text_add_button_url = State()
    photo_add_button = State()
    check_photo_1 = State()
    check_photo_1_time = State()
    check_photo_2 = State()
    check_photo_2_time = State()
    photo_add_button_text = State()
    photo_add_button_url = State()
    video_add_button = State()
    check_video_1 = State()
    check_video_1_time = State()
    check_video_2 = State()
    check_video_2_time = State()
    video_add_button_text = State()
    video_add_button_url = State()
    check_video_note_1 = State()
    check_video_note_1_time = State()


@router.callback_query(F.data == 'send', StateFilter(default_state), F.from_user.id.in_(ADMIN_IDS))
async def send_to_all(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(text='📝 Сейчас мы подготовим сообщение для рассылки по юзерам!\n'
                              'Отправьте пожалуйста текстовое сообщение 📨 или картинку 🖼️ (можно с текстом) или видео 🎥 (можно с текстом) или видео-кружок ⭕')
    await state.set_state(FSMFillForm.send)


#Создание текстового сообщения


@router.message(F.text, StateFilter(FSMFillForm.send), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    await message.answer(text='🔗 Добавим кнопку-ссылку?', reply_markup=create_kb(2, yes='✅ Да', no='❌ Нет'))
    await state.set_state(FSMFillForm.text_add_button)


@router.callback_query(F.data == 'no', StateFilter(FSMFillForm.text_add_button), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button_no(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    await cb.message.answer(text='👀 Проверьте ваше сообщение для отправки')
    await cb.message.answer(text=dct['text'])
    await cb.message.answer(text='✅ Оформление верно?', reply_markup=create_kb(2, yes='✅ Да', no='❌ Нет, сброс'))
    await state.set_state(FSMFillForm.check_text_1)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_text_1), F.from_user.id.in_(ADMIN_IDS))
async def check_text_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='📅 Введите дату и время отправки в формате ДД.ММ.ГГ ЧЧ.ММ или отправьте сейчас',
                            reply_markup=create_kb(1, now='🚀 Отправить сейчас'))
    await state.set_state(FSMFillForm.check_text_1_time)


@router.message(StateFilter(FSMFillForm.check_text_1_time), F.from_user.id.in_(ADMIN_IDS))
async def check_text_yes_1_time(msg: Message, state: FSMContext):
    try:
        # Парсим и валидируем дату
        send_time = datetime.strptime(msg.text, '%d.%m.%y %H.%M')

        # Проверяем что дата не в прошлом
        if send_time <= datetime.now():
            await msg.answer("❌ Дата должна быть в будущем! Введите корректную дату:")
            return

        dct = await state.get_data()
        async with Session() as session:
            post = Post(
                type="text",
                text=dct['text'],
                send_at=send_time
            )
            session.add(post)
            await session.commit()

        await msg.answer(f"✅ Пост запланирован на {send_time.strftime('%d.%m.%Y %H:%M')}",
                         reply_markup=admin_keyboard)
        await state.clear()

    except ValueError:
        await msg.answer("❌ Неверный формат даты! Используйте ДД.ММ.ГГ ЧЧ.ММ (например: 25.12.23 15.30)")


@router.callback_query(F.data == 'now', StateFilter(FSMFillForm.check_text_1_time), F.from_user.id.in_(ADMIN_IDS))
async def check_text_yes_1_time(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            await asyncio.sleep(0.2)
            await bot.send_message(user_id, text=dct['text'])
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'✅ Сообщение отправлено {count} юзерам', reply_markup=admin_keyboard)
    await state.set_state(default_state)
    await state.clear()


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.text_add_button), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='✏️ Введите текст кнопки-ссылки')
    await state.set_state(FSMFillForm.text_add_button_text)


@router.message(F.text, StateFilter(FSMFillForm.text_add_button_text), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button_yes_2(message: types.Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await message.answer(text='🔗 Теперь введите корректный url (ссылка на сайт, телеграмм)')
    await state.set_state(FSMFillForm.text_add_button_url)


@router.message(F.text, StateFilter(FSMFillForm.text_add_button_url), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button_yes_3(message: types.Message, state: FSMContext):
    await state.update_data(button_url=message.text)
    dct = await state.get_data()
    try:
        await message.answer(text='👀 Проверьте ваше сообщение для отправки')
        await message.answer(text=dct['text'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
        await message.answer(text='✅ Оформление верно?', reply_markup=create_kb(2, yes='✅ Да', no='❌ Нет, сброс'))
        await state.set_state(FSMFillForm.check_text_2)
    except Exception:
        await message.answer(text='❌ Скорее всего вы ввели не корректный url. Направьте корректный url')
        await state.set_state(FSMFillForm.text_add_button_url)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_text_2), F.from_user.id.in_(ADMIN_IDS))
async def check_text_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='📅 Введите дату и время отправки в формате ДД.ММ.ГГ ЧЧ.ММ или отправьте сейчас',
                            reply_markup=create_kb(1, now='🚀 Отправить сейчас'))
    await state.set_state(FSMFillForm.check_text_2_time)


@router.message(StateFilter(FSMFillForm.check_text_2_time), F.from_user.id.in_(ADMIN_IDS))
async def check_text_yes_1_time(msg: Message, state: FSMContext):
    try:
        # Парсим и валидируем дату
        send_time = datetime.strptime(msg.text, '%d.%m.%y %H.%M')

        # Проверяем что дата не в прошлом
        if send_time <= datetime.now():
            await msg.answer("❌ Дата должна быть в будущем! Введите корректную дату:")
            return

        dct = await state.get_data()
        async with Session() as session:
            post = Post(
                type="text",
                text=dct['text'],
                button_text=dct['button_text'],
                button_link=dct['button_url'],
                send_at=send_time
            )
            session.add(post)
            await session.commit()

        await msg.answer(f"✅ Пост запланирован на {send_time.strftime('%d.%m.%Y %H:%M')}",
                         reply_markup=admin_keyboard)
        await state.clear()

    except ValueError:
        await msg.answer("❌ Неверный формат даты! Используйте ДД.ММ.ГГ ЧЧ.ММ (например: 25.12.23 15.30)")


@router.callback_query(F.data == 'now', StateFilter(FSMFillForm.check_text_2_time), F.from_user.id.in_(ADMIN_IDS))
async def check_text_yes_2(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            await asyncio.sleep(0.2)
            await bot.send_message(user_id, text=dct['text'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'✅ Сообщение отправлено {count} юзерам', reply_markup=admin_keyboard)
    await state.set_state(default_state)
    await state.clear()


#Создание фото-сообщения


@router.message(F.photo, StateFilter(FSMFillForm.send), F.from_user.id.in_(ADMIN_IDS))
async def photo_add_button(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    try:
        await state.update_data(caption=message.caption)
    except Exception:
        pass
    await message.answer(text='🔗 Добавим кнопку-ссылку?', reply_markup=create_kb(2, yes='✅ Да', no='❌ Нет'))
    await state.set_state(FSMFillForm.photo_add_button)


@router.callback_query(F.data == 'no', StateFilter(FSMFillForm.photo_add_button), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button_no(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    await cb.message.answer(text='👀 Проверьте ваше сообщение для отправки')
    if dct.get('caption'):
        await cb.message.answer_photo(photo=dct['photo_id'], caption=dct['caption'])
    else:
        await cb.message.answer_photo(photo=dct['photo_id'])
    await cb.message.answer(text='✅ Оформление верно?', reply_markup=create_kb(2, yes='✅ Да', no='❌ Нет, сброс'))
    await state.set_state(FSMFillForm.check_photo_1)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_photo_1), F.from_user.id.in_(ADMIN_IDS))
async def check_photo_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='📅 Введите дату и время отправки в формате ДД.ММ.ГГ ЧЧ.ММ или отправьте сейчас',
                            reply_markup=create_kb(1, now='🚀 Отправить сейчас'))
    await state.set_state(FSMFillForm.check_photo_1_time)


@router.message(StateFilter(FSMFillForm.check_photo_1_time), F.from_user.id.in_(ADMIN_IDS))
async def check_photo_yes_1_time(msg: Message, state: FSMContext):
    try:
        # Парсим и валидируем дату
        send_time = datetime.strptime(msg.text, '%d.%m.%y %H.%M')

        # Проверяем что дата не в прошлом
        if send_time <= datetime.now():
            await msg.answer("❌ Дата должна быть в будущем! Введите корректную дату:")
            return

        dct = await state.get_data()
        async with Session() as session:
            post = Post(
                type="photo",
                media=dct['photo_id'],
                text=dct.get('caption'),
                send_at=send_time
            )
            session.add(post)
            await session.commit()

        await msg.answer(f"✅ Пост запланирован на {send_time.strftime('%d.%m.%Y %H:%M')}",
                         reply_markup=admin_keyboard)
        await state.clear()

    except ValueError:
        await msg.answer("❌ Неверный формат даты! Используйте ДД.ММ.ГГ ЧЧ.ММ (например: 25.12.23 15.30)")


@router.callback_query(F.data == 'now', StateFilter(FSMFillForm.check_photo_1_time), F.from_user.id.in_(ADMIN_IDS))
async def check_photo_yes_1(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            await asyncio.sleep(0.2)
            if dct.get('caption'):
                await bot.send_photo(user_id, photo=dct['photo_id'], caption=dct['caption'])
            else:
                await bot.send_photo(user_id, photo=dct['photo_id'])
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'✅ Сообщение отправлено {count} юзерам', reply_markup=admin_keyboard)
    await state.set_state(default_state)
    await state.clear()


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.photo_add_button), F.from_user.id.in_(ADMIN_IDS))
async def photo_add_button_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='✏️ Введите текст кнопки-ссылки')
    await state.set_state(FSMFillForm.photo_add_button_text)


@router.message(F.text, StateFilter(FSMFillForm.photo_add_button_text), F.from_user.id.in_(ADMIN_IDS))
async def photo_add_button_yes_2(message: types.Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await message.answer(text='🔗 Теперь введите корректный url (ссылка на сайт, телеграмм)')
    await state.set_state(FSMFillForm.photo_add_button_url)


@router.message(F.text, StateFilter(FSMFillForm.photo_add_button_url), F.from_user.id.in_(ADMIN_IDS))
async def photo_add_button_yes_3(message: types.Message, state: FSMContext):
    await state.update_data(button_url=message.text)
    dct = await state.get_data()
    try:
        await message.answer(text='👀 Проверьте ваше сообщение для отправки')
        if dct.get('caption'):
            await message.answer_photo(photo=dct['photo_id'], caption=dct['caption'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
        else:
            await message.answer_photo(photo=dct['photo_id'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
        await message.answer(text='✅ Оформление верно?', reply_markup=create_kb(2, yes='✅ Да', no='❌ Нет, сброс'))
        await state.set_state(FSMFillForm.check_photo_2)
    except Exception as e:
        print(e)
        await message.answer(text='❌ Скорее всего вы ввели не корректный url. Направьте корректный url')
        await state.set_state(FSMFillForm.photo_add_button_url)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_photo_2), F.from_user.id.in_(ADMIN_IDS))
async def check_photo_yes_2(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='📅 Введите дату и время отправки в формате ДД.ММ.ГГ ЧЧ.ММ или отправьте сейчас',
                            reply_markup=create_kb(1, now='🚀 Отправить сейчас'))
    await state.set_state(FSMFillForm.check_photo_2_time)


@router.message(StateFilter(FSMFillForm.check_photo_2_time), F.from_user.id.in_(ADMIN_IDS))
async def check_photo_yes_2_time(msg: Message, state: FSMContext):
    try:
        # Парсим и валидируем дату
        send_time = datetime.strptime(msg.text, '%d.%m.%y %H.%M')

        # Проверяем что дата не в прошлом
        if send_time <= datetime.now():
            await msg.answer("❌ Дата должна быть в будущем! Введите корректную дату:")
            return

        dct = await state.get_data()
        async with Session() as session:
            post = Post(
                type="photo",
                media=dct['photo_id'],
                text=dct.get('caption'),
                button_text=dct['button_text'],
                button_link=dct['button_url'],
                send_at=send_time
            )
            session.add(post)
            await session.commit()

        await msg.answer(f"✅ Пост запланирован на {send_time.strftime('%d.%m.%Y %H:%M')}",
                         reply_markup=admin_keyboard)
        await state.clear()

    except ValueError:
        await msg.answer("❌ Неверный формат даты! Используйте ДД.ММ.ГГ ЧЧ.ММ (например: 25.12.23 15.30)")


@router.callback_query(F.data == 'now', StateFilter(FSMFillForm.check_photo_2_time), F.from_user.id.in_(ADMIN_IDS))
async def check_photo_yes_2(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            await asyncio.sleep(0.2)
            if dct.get('caption'):
                    await bot.send_photo(user_id, photo=dct['photo_id'], caption=dct['caption'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
            else:
                await bot.send_photo(user_id, photo=dct['photo_id'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'✅ Сообщение отправлено {count} юзерам', reply_markup=admin_keyboard)
    await state.set_state(default_state)
    await state.clear()


#Создание видео-сообщения


@router.message(F.video, StateFilter(FSMFillForm.send), F.from_user.id.in_(ADMIN_IDS))
async def video_add_button(message: types.Message, state: FSMContext):
    await state.update_data(video_id=message.video.file_id)
    try:
        await state.update_data(caption=message.caption)
    except Exception:
        pass
    await message.answer(text='🔗 Добавим кнопку-ссылку?', reply_markup=create_kb(2, yes='✅ Да', no='❌ Нет'))
    await state.set_state(FSMFillForm.video_add_button)


@router.callback_query(F.data == 'no', StateFilter(FSMFillForm.video_add_button), F.from_user.id.in_(ADMIN_IDS))
async def video_add_button_no(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    await cb.message.answer(text='👀 Проверьте ваше сообщение для отправки')
    if dct.get('caption'):
        await cb.message.answer_video(video=dct['video_id'], caption=dct['caption'])
    else:
        await cb.message.answer_video(video=dct['video_id'])
    await cb.message.answer(text='✅ Оформление верно?', reply_markup=create_kb(2, yes='✅ Да', no='❌ Нет, сброс'))
    await state.set_state(FSMFillForm.check_video_1)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_video_1), F.from_user.id.in_(ADMIN_IDS))
async def check_video_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='📅 Введите дату и время отправки в формате ДД.ММ.ГГ ЧЧ.ММ или отправьте сейчас',
                            reply_markup=create_kb(1, now='🚀 Отправить сейчас'))
    await state.set_state(FSMFillForm.check_video_1_time)


@router.message(StateFilter(FSMFillForm.check_video_1_time), F.from_user.id.in_(ADMIN_IDS))
async def check_video_yes_1_time(msg: Message, state: FSMContext):
    try:
        # Парсим и валидируем дату
        send_time = datetime.strptime(msg.text, '%d.%m.%y %H.%M')

        # Проверяем что дата не в прошлом
        if send_time <= datetime.now():
            await msg.answer("❌ Дата должна быть в будущем! Введите корректную дату:")
            return

        dct = await state.get_data()
        async with Session() as session:
            post = Post(
                type="video",
                media=dct['video_id'],
                text=dct.get('caption'),
                send_at=send_time
            )
            session.add(post)
            await session.commit()

        await msg.answer(f"✅ Пост запланирован на {send_time.strftime('%d.%m.%Y %H:%M')}",
                         reply_markup=admin_keyboard)
        await state.clear()

    except ValueError:
        await msg.answer("❌ Неверный формат даты! Используйте ДД.ММ.ГГ ЧЧ.ММ (например: 25.12.23 15.30)")


@router.callback_query(F.data == 'now', StateFilter(FSMFillForm.check_video_1_time), F.from_user.id.in_(ADMIN_IDS))
async def check_video_yes_1(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            await asyncio.sleep(0.2)
            if dct.get('caption'):
                await bot.send_video(user_id, video=dct['video_id'], caption=dct['caption'])
            else:
                await bot.send_video(user_id, video=dct['video_id'])
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'✅ Сообщение отправлено {count} юзерам', reply_markup=admin_keyboard)
    await state.set_state(default_state)
    await state.clear()


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.video_add_button), F.from_user.id.in_(ADMIN_IDS))
async def video_add_button_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='✏️ Введите текст кнопки-ссылки')
    await state.set_state(FSMFillForm.video_add_button_text)


@router.message(F.text, StateFilter(FSMFillForm.video_add_button_text), F.from_user.id.in_(ADMIN_IDS))
async def video_add_button_yes_2(message: types.Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await message.answer(text='🔗 Теперь введите корректный url (ссылка на сайт, телеграмм)')
    await state.set_state(FSMFillForm.video_add_button_url)


@router.message(F.text, StateFilter(FSMFillForm.video_add_button_url), F.from_user.id.in_(ADMIN_IDS))
async def video_add_button_yes_3(message: types.Message, state: FSMContext):
    await state.update_data(button_url=message.text)
    dct = await state.get_data()
    try:
        await message.answer(text='👀 Проверьте ваше сообщение для отправки')
        if dct.get('caption'):
            await message.answer_video(video=dct['video_id'], caption=dct['caption'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
        else:
            await message.answer_video(video=dct['video_id'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
        await message.answer(text='✅ Оформление верно?', reply_markup=create_kb(2, yes='✅ Да', no='❌ Нет, сброс'))
        await state.set_state(FSMFillForm.check_video_2)
    except Exception as e:
        print(e)
        await message.answer(text='❌ Скорее всего вы ввели не корректный url. Направьте корректный url')
        await state.set_state(FSMFillForm.video_add_button_url)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_video_2), F.from_user.id.in_(ADMIN_IDS))
async def check_video_yes_2(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='📅 Введите дату и время отправки в формате ДД.ММ.ГГ ЧЧ.ММ или отправьте сейчас',
                            reply_markup=create_kb(1, now='🚀 Отправить сейчас'))
    await state.set_state(FSMFillForm.check_video_2_time)


@router.message(StateFilter(FSMFillForm.check_video_2_time), F.from_user.id.in_(ADMIN_IDS))
async def check_video_yes_2_time(msg: Message, state: FSMContext):
    try:
        # Парсим и валидируем дату
        send_time = datetime.strptime(msg.text, '%d.%m.%y %H.%M')

        # Проверяем что дата не в прошлом
        if send_time <= datetime.now():
            await msg.answer("❌ Дата должна быть в будущем! Введите корректную дату:")
            return

        dct = await state.get_data()
        async with Session() as session:
            post = Post(
                type="video",
                media=dct['video_id'],
                text=dct.get('caption'),
                button_text=dct['button_text'],
                button_link=dct['button_url'],
                send_at=send_time
            )
            session.add(post)
            await session.commit()

        await msg.answer(f"✅ Пост запланирован на {send_time.strftime('%d.%m.%Y %H:%M')}",
                         reply_markup=admin_keyboard)
        await state.clear()

    except ValueError:
        await msg.answer("❌ Неверный формат даты! Используйте ДД.ММ.ГГ ЧЧ.ММ (например: 25.12.23 15.30)")


@router.callback_query(F.data == 'now', StateFilter(FSMFillForm.check_video_2_time), F.from_user.id.in_(ADMIN_IDS))
async def check_video_yes_2_time(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            await asyncio.sleep(0.2)
            if dct.get('caption'):
                await bot.send_video(user_id, video=dct['video_id'], caption=dct['caption'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
            else:
                await bot.send_video(user_id, video=dct['video_id'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'✅ Сообщение отправлено {count} юзерам', reply_markup=admin_keyboard)
    await state.set_state(default_state)
    await state.clear()


#Создание видео-кружка


@router.message(F.video_note, StateFilter(FSMFillForm.send), F.from_user.id.in_(ADMIN_IDS))
async def video_note_check(message: types.Message, state: FSMContext):
    await state.update_data(video_note_id=message.video_note.file_id)
    await message.answer(text='👀 Проверьте вашу запись в кружке для отправки')
    await message.answer(text='✅ Оформление верно?', reply_markup=create_kb(2, yes='✅ Да', no='❌ Нет, сброс'))
    await state.set_state(FSMFillForm.check_video_note_1)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_video_note_1), F.from_user.id.in_(ADMIN_IDS))
async def check_videonote_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='📅 Введите дату и время отправки в формате ДД.ММ.ГГ ЧЧ.ММ или отправьте сейчас',
                            reply_markup=create_kb(1, now='🚀 Отправить сейчас'))
    await state.set_state(FSMFillForm.check_video_note_1_time)


@router.message(StateFilter(FSMFillForm.check_video_note_1_time), F.from_user.id.in_(ADMIN_IDS))
async def check_videonote_yes_1_time(msg: Message, state: FSMContext):
    try:
        # Парсим и валидируем дату
        send_time = datetime.strptime(msg.text, '%d.%m.%y %H.%M')

        # Проверяем что дата не в прошлом
        if send_time <= datetime.now():
            await msg.answer("❌ Дата должна быть в будущем! Введите корректную дату:")
            return

        dct = await state.get_data()
        async with Session() as session:
            post = Post(
                type="videonote",
                media=dct['video_note_id'],
                send_at=send_time
            )
            session.add(post)
            await session.commit()

        await msg.answer(f"✅ Пост запланирован на {send_time.strftime('%d.%m.%Y %H:%M')}",
                         reply_markup=admin_keyboard)
        await state.clear()

    except ValueError:
        await msg.answer("❌ Неверный формат даты! Используйте ДД.ММ.ГГ ЧЧ.ММ (например: 25.12.23 15.30)")


@router.callback_query(F.data == 'now', StateFilter(FSMFillForm.check_video_note_1_time), F.from_user.id.in_(ADMIN_IDS))
async def check_video_note_yes_1_time(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            await asyncio.sleep(0.2)
            await bot.send_video_note(user_id, video_note=dct['video_note_id'])
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'✅ Сообщение отправлено {count} юзерам', reply_markup=admin_keyboard)
    await state.set_state(default_state)
    await state.clear()


# Выход из рассылки без отправки


@router.callback_query(F.data == 'no', StateFilter(FSMFillForm.check_text_1, FSMFillForm.check_text_2,
                       FSMFillForm.check_photo_1, FSMFillForm.check_photo_2, FSMFillForm.check_video_1,
                       FSMFillForm.check_video_2, FSMFillForm.check_video_note_1), F.from_user.id.in_(ADMIN_IDS))
async def check_message_no(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text=f'❌ Сообщение не отправлено', reply_markup=admin_keyboard)
    await cb.answer()
    await state.set_state(default_state)
    await state.clear()
