import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from models import User, BotState


class State:
    LOGIN_NAME = 1
    LOGIN_REQUISITES = 2
    CHANGE_DATA_NAME = 3
    CHANGE_DATA_REQUISITES = 4
    END = ConversationHandler.END


class Callback:
    BACK = "^back$"


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        if await User.find_by_tg_id(str(update.message.from_user.id)):
            await update.message.reply_text(
                "Ты уже зареган. Назад пути нет",
            )
            return State.END

        user_id = await User.create(
            tg_id=str(update.message.from_user.id),
            name="",
        )
        await BotState.create(user_id)
        await update.message.reply_text(
            "Это бот для дележки чеков олгошей\nВведи имя, которое будет "
            "отображаться у других",
        )
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Это бот для дележки чеков олгошей\nВведи имя, которое будет "
            "отображаться у других",
        )
    return State.LOGIN_NAME


async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author['_id'])
    if await User.check_name_exists(update.message.text):
        await update.message.reply_text("Это имя занято")
        return State.LOGIN_NAME

    await User.edit_name(user_id, name=update.message.text)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back")]])
    await update.message.reply_text(
        "Теперь введи реквизиты (например +79876543210 тинька)",
        reply_markup=keyboard,
    )
    return State.LOGIN_REQUISITES


async def requisites_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.callback_query.from_user.id))
    user_id = str(author['_id'])
    await User.edit_name(user_id, '')
    return await login(update, context)


async def requisites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author['_id'])
    await User.edit_requisites(user_id, requisites=update.message.text)
    await update.message.reply_text(
        "Бот готов к использованию, за дальнейшими инструкциями напиши /help",
    )
    return State.END


async def change_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author['_id'])
    await update.message.reply_text(
        f"Введи имя, которое будет отображаться у других. Сейчас у тебя имя {author['name']}",
    )
    return State.CHANGE_DATA_NAME


async def change_data_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author['_id'])
    await User.edit_name(user_id, '')

    if await User.check_name_exists(update.message.text):
        await update.message.reply_text("Это имя занято")
        return State.CHANGE_DATA_NAME

    await User.edit_name(user_id, name=update.message.text)
    await update.message.reply_text(
        f"Имя изменено на {update.message.text}",
    )
    return State.END


async def change_requisites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author['_id'])
    await update.message.reply_text(
        f"Введи новые реквизиты. Сейчас у тебя они {author['requisites']}",
    )
    return State.CHANGE_DATA_REQUISITES


async def change_data_requisites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author['_id'])
    await User.edit_requisites(user_id, requisites=update.message.text)
    await update.message.reply_text(
        f"Реквизиты изменены на {update.message.text}",
    )
    return State.END


async def login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author['_id'])
    await User.delete(user_id)
    await update.message.reply_text(
        "Ты вычеркнут из списка юзеров",
    )
    return State.END


async def change_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Окей. Отмена, так отмена",
    )
    return State.END


async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    while user := await User.find_by_tg_id(str(update.message.from_user.id)):
        await User.delete(user['_id'])


delete_user_handler = CommandHandler("delete_user", delete_user)
login_handler = ConversationHandler(
    entry_points=[CommandHandler("start", login)],
    states={
        State.LOGIN_NAME: [
            MessageHandler(filters.TEXT, name),
        ],
        State.LOGIN_REQUISITES: [
            MessageHandler(filters.TEXT, requisites),
            CallbackQueryHandler(requisites_back, pattern=Callback.BACK),
        ],
    },
    fallbacks=[CommandHandler("cancel", login_cancel)],
)
change_name_handler = ConversationHandler(
    entry_points=[CommandHandler("change_name", change_name)],
    states={
        State.CHANGE_DATA_NAME: [
            MessageHandler(filters.TEXT, change_data_name),
        ],
    },
    fallbacks=[CommandHandler("cancel", change_cancel)],
)
change_requisites_handler = ConversationHandler(
    entry_points=[CommandHandler("change_requisites", change_requisites)],
    states={
        State.CHANGE_DATA_REQUISITES: [
            MessageHandler(filters.TEXT, change_data_requisites),
        ],
    },
    fallbacks=[CommandHandler("cancel", change_cancel)],
)
handlers = [login_handler, change_name_handler, change_requisites_handler, delete_user_handler]
