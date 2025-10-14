import gspread
from oauth2client.service_account import ServiceAccountCredentials
from sqlalchemy import select

from db.models import Session, Question, User, Event, Review, Post

# Данные для доступа к Google Таблице
SERVICE_ACCOUNT_FILE = 'creds.json'
SCOPE = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
SPREADSHEET_ID = '1TBHeRxmZPLUHmYsPRvqmSqR9hel2B-mudFUyIRsk1fw'


# Функция для авторизации в Google Таблицах
async def get_sheet():
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        SERVICE_ACCOUNT_FILE, SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    return sheet


# Добавьте этот код в posting.py после импортов и перед функцией scheduler

async def prepare_sheet_data():
    """Формирует данные для выгрузки в Google Таблицу"""
    rows = []

    async with Session() as session:
        # Раздел ВОПРОСЫ
        rows.append(['Вопросы'])
        rows.append(
            ['№', 'Текст вопроса', 'Когда создан', 'user_id', 'username', 'first_name', 'last_name', 'Текст ответа',
             'Когда ответ'])

        result = await session.execute(
            select(Question, User)
            .join(User, Question.user_id == User.user_id)
            .order_by(Question.created_at.desc())
        )
        questions = result.all()

        for i, (question, user) in enumerate(questions, 1):
            rows.append([
                i,
                question.question,
                question.created_at.strftime('%Y-%m-%d %H:%M:%S') if question.created_at else '',
                question.user_id,
                user.username or '',
                user.first_name or '',
                user.last_name or '',
                question.answer or '',
                question.answered_at.strftime('%Y-%m-%d %H:%M:%S') if question.answered_at else ''
            ])

        # Пустая строка
        rows.append([''])

        # Раздел МЕРОПРИЯТИЯ
        rows.append(['Мероприятия'])
        rows.append(['№', 'Название', 'Описание', 'Дата проведения', 'Ссылка на видео'])

        result = await session.execute(
            select(Event).order_by(Event.event_date.desc())
        )
        events = result.scalars().all()

        for i, event in enumerate(events, 1):
            rows.append([
                i,
                event.title,
                event.description,
                event.event_date.strftime('%Y-%m-%d %H:%M:%S') if event.event_date else '',
                event.video_url or ''
            ])

        # Пустая строка
        rows.append([''])

        # Раздел ОТЗЫВЫ
        rows.append(['Отзывы'])
        rows.append(['№', 'Текст отзыва', 'Дата написания', 'user_id', 'username', 'first_name', 'last_name',
                     'Название мероприятия', 'Дата проведения мероприятия'])

        result = await session.execute(
            select(Review, User, Event)
            .join(User, Review.user_id == User.user_id)
            .join(Event, Review.event_id == Event.id)
            .order_by(Review.created_at.desc())
        )
        reviews = result.all()

        for i, (review, user, event) in enumerate(reviews, 1):
            rows.append([
                i,
                review.text,
                review.created_at.strftime('%Y-%m-%d %H:%M:%S') if review.created_at else '',
                review.user_id,
                user.username or '',
                user.first_name or '',
                user.last_name or '',
                event.title,
                event.event_date.strftime('%Y-%m-%d %H:%M:%S') if event.event_date else ''
            ])

        # Пустая строка
        rows.append([''])

        # Раздел ОТЛОЖЕННЫЕ ПОСТЫ
        rows.append(['Отложенные посты'])
        rows.append(['№', 'Тип поста', 'Медиа', 'Текст', 'Текст кнопки', 'Ссылка кнопки', 'Время отправки', 'Отправлено'])

        result = await session.execute(
            select(Post).order_by(Post.send_at.desc())
        )
        posts = result.scalars().all()

        for i, post in enumerate(posts, 1):
            rows.append([
                i,
                post.type,
                post.media or '',
                post.text or '',
                post.button_text or '',
                post.button_link or '',
                post.send_at.strftime('%Y-%m-%d %H:%M:%S') if post.send_at else '',
                'Да' if post.flag else 'Нет'
            ])

        # Пустая строка
        rows.append([''])

        # Раздел ЮЗЕРЫ
        rows.append(['Юзеры'])
        rows.append(['№', 'user_id', 'username', 'first_name', 'last_name', 'is_block'])

        result = await session.execute(
            select(User).order_by(User.user_id)
        )
        users = result.scalars().all()

        for i, user in enumerate(users, 1):
            rows.append([
                i,
                user.user_id,
                user.username or '',
                user.first_name or '',
                user.last_name or '',
                'Да' if user.user_is_block else 'Нет'
            ])

    return rows
