from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Это бот для дележки чеков между олгошами. Вводишь /add_pobor, затем "
        "скидываешь qr или декоженный qr, добавляешь людей и делишь вещи из "
        "чека между ними. Им потом отправится сообщение с суммой, которую они "
        "тебе должны. Ну если заплатят, то тебе придет сообщение, сможешь "
        "подтвердить платеж\nЕще можешь сам посмотреть, сколько, кому и за что "
        "ты должен или уже заплатил\nВ общем бот автоматизирует процесс побора "
        "денег с Карповых"
    )


help_handler = CommandHandler('help', help)
handlers = [help_handler]
