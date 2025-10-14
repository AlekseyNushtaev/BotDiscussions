from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру для администратора с основными командами
    """
    buttons = [
        [KeyboardButton(text="📊 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вопросы", callback_data="admin_questions")],
            [InlineKeyboardButton(text="Мероприятия", callback_data="admin_events")],
            [InlineKeyboardButton(text="Рассылка", callback_data="send")]
        ]
    )


def create_kb(width: int,
                     *args: str,
                     **kwargs: str) -> InlineKeyboardMarkup:
    # Инициализируем билдер
    kb_builder = InlineKeyboardBuilder()
    # Инициализируем список для кнопок
    buttons: list[InlineKeyboardButton] = []

    # Заполняем список кнопками из аргументов args и kwargs
    if args:
        pass
    if kwargs:
        for button, text in kwargs.items():
            buttons.append(InlineKeyboardButton(
                text=text,
                callback_data=button))

    # Распаковываем список с кнопками в билдер методом row c параметром width
    kb_builder.row(*buttons, width=width)

    # Возвращаем объект инлайн-клавиатуры
    return kb_builder.as_markup()


def kb_button(button_text, button_url):
    button = InlineKeyboardButton(text=button_text, url=button_url)
    kb = InlineKeyboardMarkup(inline_keyboard=[[button]])
    return kb