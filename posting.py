import asyncio
import datetime

from sqlalchemy import select, delete, update

from bot import bot
from config import ADMIN_IDS
from db.models import Session, Post
from handlers_admin import get_all_users_unblock
from keyboard import kb_button, admin_keyboard
from spread import get_sheet, prepare_sheet_data


async def scheduler(hour):
    await asyncio.sleep(10)
    old = hour
    while True:
        try:
            if datetime.datetime.now().hour != old:
                print(old, datetime.datetime.now().hour)
                old = datetime.datetime.now().hour
                sheet = await get_sheet()
                sheet.clear()
                load_rows = await prepare_sheet_data()
                sheet.append_rows(load_rows)
        except Exception as e:
            await bot.send_message(1012882762, str(e))
        try:
            time_now = datetime.datetime.now()
            users = await get_all_users_unblock()
            users.extend(ADMIN_IDS)
            async with Session() as db:
                result = await db.execute(select(Post).where(Post.flag == False))
                # Преобразование результата в множество уникальных ID
            for post in result.scalars():
                if post.send_at < time_now and (post.send_at + datetime.timedelta(minutes=10) > time_now):
                    count = 0
                    for user_id in users:
                        await asyncio.sleep(0.2)
                        try:
                            if post.type == 'text':
                                if post.button_text:
                                    await bot.send_message(user_id,
                                                           text=post.text,
                                                           reply_markup=kb_button(post.button_text,
                                                                                  post.button_link))
                                else:
                                    await bot.send_message(user_id,
                                                           text=post.text)
                            elif post.type == 'photo':
                                if post.button_text:
                                    if post.text:
                                        await bot.send_photo(user_id,
                                                             photo=post.media,
                                                             caption=post.text,
                                                             reply_markup=kb_button(post.button_text,
                                                                                    post.button_link))
                                    else:
                                        await bot.send_photo(user_id,
                                                             photo=post.media,
                                                             reply_markup=kb_button(post.button_text,
                                                                                    post.button_link))
                                else:
                                    if post.text:
                                        await bot.send_photo(user_id,
                                                             photo=post.media,
                                                             caption=post.text)
                                    else:
                                        await bot.send_photo(user_id,
                                                             photo=post.media)
                            elif post.type == 'video':
                                if post.button_text:
                                    if post.text:
                                        await bot.send_video(user_id,
                                                             video=post.media,
                                                             caption=post.text,
                                                             reply_markup=kb_button(post.button_text,
                                                                                    post.button_link))
                                    else:
                                        await bot.send_video(user_id,
                                                             video=post.media,
                                                             reply_markup=kb_button(post.button_text,
                                                                                    post.button_link))
                                else:
                                    if post.text:
                                        await bot.send_video(user_id,
                                                             video=post.media,
                                                             caption=post.text)
                                    else:
                                        await bot.send_video(user_id,
                                                             video=post.media)
                            elif post.type == 'videonote':
                                await bot.send_video_note(user_id,
                                                          video_note=post.media)
                            count += 1
                        except Exception as e:
                            await bot.send_message(1012882762, str(e))
                            await bot.send_message(1012882762, str(user_id))

                    async with Session() as session:
                        await session.execute(update(Post).where(Post.id == post.id).values(flag=True))
                        await session.commit()
                    for admin_id in ADMIN_IDS:
                        await bot.send_message(admin_id,
                                               text=f'✅ Отложенное сообщение отправлено {count} юзерам',
                                               reply_markup=admin_keyboard)
        except Exception as e:
            await bot.send_message(1012882762, str(e))
        await asyncio.sleep(10)
