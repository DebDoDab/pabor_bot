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

from invoice_decode import decode_qr
from models import BotState, Invoice, Item, User, Operation

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class State:
    PABOR_QR = 1
    PABOR_INVOICE_GROUP = 2  # "pabor_invoice_{invoice_id}_group"
    PABOR_INVOICE_ITEM = 3  # "pabor_invoice_{invoice_id}_item_{item_id}"
    PABOR_INVOICE_NAME = 4  # "pabor_invoice_{invoice_id}_name"
    PABOR_INVOICE_VERIFICATION = 5  # "pabor_invoice_{invoice_id}_verification"
    PABOR_INVOICE_CHANGE_GROUP = 6  # "pabor_invoice_{invoice_id}_change_group"
    PABOR_INVOICE_CHANGE_ITEMS = 7  # "pabor_invoice_{invoice_id}_change_items"
    PABOR_INVOICE_CHANGE_ITEM = 8  # "pabor_invoice_{invoice_id}_change_item_{item_id}"
    PABOR_INVOICE_CHANGE_NAME = 9  # "pabor_invoice_{invoice_id}_change_name"
    PABOR_INVOICE_CHANGE_CANCEL = 10  # "pabor_invoice_{invoice_id}_change_cancel"
    END = ConversationHandler.END


class Callback:
    BACK = "^back$"
    READY = "^ready$"
    INVOICE_GROUP_USER = "^invoice_group_user_(.+)$"
    INVOICE_ITEM_USER = "^invoice_item_user_(.+)_(plus|minus)?$"
    INVOICE_CHANGE_GROUP = "^invoice_change_group$"
    INVOICE_CHANGE_ITEMS = "^invoice_change_items$"
    INVOICE_CHANGE_NAME = "^invoice_change_name$"
    INVOICE_CHANGE_ITEM = "^invoice_change_item_(.*)$"
    PAID_OPERATION = "^paid_operation_(.+)$"
    ACCEPT_OPERATION = "^accept_operation_(.+)$"
    DECLINE_OPERATION = "^decline_operation_(.+)$"


async def new_pabor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author.get('_id'))
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Назад", callback_data="back")]]
    )
    await update.message.reply_text(
        f"Скинь qr или дешефрованный qr", reply_markup=keyboard  # TODO: add items manually
    )
    return State.PABOR_QR


async def qr_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    await query.edit_message_text(text=f"Okej")
    return State.END


async def qr_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author.get('_id'))
    photo_file = await update.message.photo[-1].get_file()
    await photo_file.download(f"user_{user_id}_qr.jpg")
    qr = "random_qr_string"  # TODO: decode qr photo
    return await _qr(update, context, qr)


async def qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qr = update.message.text
    return await _qr(update, context, qr)


async def _qr(update: Update, context: ContextTypes.DEFAULT_TYPE, qr: str):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author.get('_id'))
    try:
        invoice = await decode_qr(qr)
    except Exception:  # TODO: catch exceptions
        await update.message.reply_text(
            f"Скрипт Ильи сломался, пусть починит",
        )
        return State.END

    if not invoice.get('items', []):
        await update.message.reply_text(
            "Чек пустой. Ты придурок?"
        )
        return State.END

    await update.message.reply_text(
        '\n'.join(
            list(map(lambda x: f"{x.get('total_price')}\t{x.get('name')}", invoice.get('items'))),
        ),
    )

    invoice_id = await Invoice.create(
        total_cost=invoice.get('total_cost'),
        owner_id=user_id,
        items_ids=[
            await Item.create(
                total_price=item.get('total_price'),
                name=item.get('name'),
                details=item.get('details'),
            )
            for item in invoice.get('items')
        ],
        users_group=[user_id],
    )
    await BotState.edit(user_id, invoice_id=invoice_id)

    await update.message.reply_text(
        f"Кто причастен к этой покупке?",
        reply_markup=await _get_group_buttons(invoice_id),
    )
    return State.PABOR_INVOICE_GROUP


async def invoice_group_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(update.callback_query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    await Invoice.delete(invoice_id)
    await BotState.edit(user_id)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Назад", callback_data="back")]]
    )
    await query.edit_message_text(
        f"Скинь qr или дешефрованный qr", reply_markup=keyboard,
    )
    return State.PABOR_QR


async def invoice_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    invoice_id = (await BotState.find_by_user_id(user_id)).get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    paying_users = invoice.get('users_owe', {})
    users_group = invoice.get('users_group')

    try:
        button_user_id = re.match(Callback.INVOICE_GROUP_USER, query.data).group(1)
    except (IndexError, AttributeError):
        button_user_id = None

    if button_user_id and button_user_id in users_group and button_user_id != user_id and button_user_id not in paying_users:
        await Invoice.remove_user_from_group(invoice_id, button_user_id)
    if button_user_id and button_user_id not in users_group:
        await Invoice.add_user_to_group(invoice_id, button_user_id)

    await query.edit_message_text(
        f"Кто причастен к этой покупке?",
        reply_markup=await _get_group_buttons(invoice_id),
    )

    return State.PABOR_INVOICE_GROUP


async def _get_group_buttons(invoice_id, back_button: bool = True) -> InlineKeyboardMarkup:
    invoice = await Invoice.find_by_id(invoice_id)
    users_group = invoice.get('users_group', [])
    users = await User.get_all()

    buttons = [
        [
            InlineKeyboardButton(
                user.get('name') + ("✓" if str(user['_id']) in users_group else ""),
                callback_data=f"invoice_group_user_{str(user['_id'])}",
            )
        ]
        for user in users
    ]

    last_line = []
    if back_button:
        last_line.append(InlineKeyboardButton("Назад", callback_data="back"))
    if users_group:
        last_line.append(InlineKeyboardButton("Готово", callback_data="ready"))
    buttons.append(last_line)

    return InlineKeyboardMarkup(buttons)


async def invoice_group_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    items_ids = invoice.get('items_ids')
    item_id = items_ids[0]
    await BotState.edit(user_id, invoice_id, item_id)

    return await invoice_item(update, context)


async def invoice_item_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    items_ids = invoice.get('items_ids')
    item_id = bot_state.get('item_id')

    if item_id != items_ids[0]:
        prev_item_id = items_ids[items_ids.index(item_id) - 1]
        await BotState.edit(user_id, invoice_id, prev_item_id)
        return await invoice_item(update, context)
    else:
        await BotState.edit(user_id, invoice_id, None)
        return await invoice_group(update, context)


async def invoice_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    item_id = bot_state.get('item_id')
    item = await Item.find_by_id(item_id)
    item_division = item.get('users_division', {})

    try:
        button_user_id = re.match(Callback.INVOICE_ITEM_USER, query.data).group(1)
        diff = re.match(Callback.INVOICE_ITEM_USER, query.data).group(2)
    except (IndexError, AttributeError):
        button_user_id = None
        diff = None

    if (
            diff == "minus" and
            item_division.get(button_user_id, None)
    ):
        await Item.edit_user_division(
            item_id, button_user_id, item_division[button_user_id] - 1,
        )
    elif diff == "plus":
        await Item.edit_user_division(
            item_id, button_user_id, item_division.get(button_user_id, 0) + 1,
        )

    if button_user_id:
        await _recalculate_users_owe(invoice_id)

    await query.edit_message_text(
        f"Между кем делить?\n"
        f"{item.get('name')}\n{item.get('details')}\nЦена = {item.get('total_price')}?",
        reply_markup=await _get_item_buttons(invoice_id, item_id),
    )

    return State.PABOR_INVOICE_ITEM


async def _recalculate_users_owe(invoice_id):
    invoice = await Invoice.find_by_id(invoice_id)
    items_ids = invoice.get('items_ids')
    users_owe = {}
    for item_id in items_ids:
        item = await Item.find_by_id(item_id)
        item_division = item.get('users_division')
        total_count = sum(item_division.values())
        if not total_count:
            continue
        for user_id, user_count in item_division.items():
            if user_id not in users_owe:
                users_owe[user_id] = 0.
            users_owe[user_id] += item.get('total_price') * (float(user_count) / float(total_count))

    for user_id, user_total in users_owe.items():
        await Invoice.edit_user_owe(invoice_id, user_id, user_total)


async def _get_item_buttons(invoice_id, item_id, cancel_button: bool = True) -> InlineKeyboardMarkup:
    invoice = await Invoice.find_by_id(invoice_id)
    users = invoice.get('users_group')
    item = await Item.find_by_id(item_id)
    item_division = item.get('users_division')
    total_count = sum(item_division.values())
    buttons = []
    for user_id in users:
        user = await User.find_by_id(user_id)
        buttons.append([
            InlineKeyboardButton("-1", callback_data=f"invoice_item_user_{user_id}_minus"),
            InlineKeyboardButton(user.get('name') + str(item_division.get(user_id, 0)) + "/" + str(total_count), callback_data=f'invoice_item_user_{user_id}_'),
            InlineKeyboardButton("+1", callback_data=f"invoice_item_user_{user_id}_plus"),
        ])

    last_line = []
    if cancel_button:
        last_line.append(InlineKeyboardButton("Назад", callback_data='back'))
    if total_count:
        last_line.append(InlineKeyboardButton("Готово", callback_data='ready'))
    buttons.append(last_line)

    return InlineKeyboardMarkup(buttons)


async def invoice_item_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    items_ids = invoice.get('items_ids')
    item_id = bot_state.get('item_id')

    if item_id != items_ids[-1]:
        next_item_id = items_ids[items_ids.index(item_id) + 1]
        await BotState.edit(user_id, invoice_id, next_item_id)
        return await invoice_item(update, context)

    await query.answer()
    await BotState.edit(user_id, invoice_id=invoice_id)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back")]])
    await query.edit_message_text(f"Введи имя покупки", reply_markup=keyboard)

    return State.PABOR_INVOICE_NAME


async def invoice_name_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    items_ids = invoice.get('items_ids')
    await BotState.edit(user_id, invoice_id, items_ids[-1])
    return await invoice_item(update, context)

    
async def invoice_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')

    await Invoice.edit_name(invoice_id, update.message.text)
    return await invoice_verification(update, context)


async def invoice_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        author = await User.find_by_tg_id(str(query.from_user.id))
        await query.answer()
    else:
        author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    users_group = invoice.get('users_group')
    users = [await User.find_by_id(user_id) for user_id in users_group]

    response_message = "Все сделано, проверь данные\n"
    response_message += f"Название покупки - {invoice.get('name')}\n"

    users_names = [user.get('name') for user in users]
    response_message += f"Причастны к покупке - {', '.join(users_names)}\n"

    response_message += f"Деняк должны -\n"
    for user_id, user_total in invoice.get('users_owe').items():
        user = await User.find_by_id(user_id)
        response_message += f"{user['name']} -> {user_total}\n"

    response_message += "\n\n"
    response_message += "Айтемы из чека -"
    for item_id in invoice.get('items_ids'):
        item = await Item.find_by_id(item_id)
        response_message += f"\n{item.get('name')} стоит {item.get('total_price')}. За него должны\n\t"
        total_count = sum(item.get('users_division').values())
        for user_id, user_count in item.get('users_division').items():
            if user_count == 0:
                continue
            user = await User.find_by_id(user_id)
            response_message += f"{user.get('name')} -> {item.get('total_price') * (float(user_count) / float(total_count))}\n"

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Изменить группу", callback_data="invoice_change_group")],
            [InlineKeyboardButton("Изменить распределение товаров", callback_data="invoice_change_items")],
            [InlineKeyboardButton("Изменить название", callback_data="invoice_change_name")],
            [InlineKeyboardButton("Готово", callback_data="ready")],
            [InlineKeyboardButton("Отменить чек", callback_data="back")],
        ]
    )
    if query:
        await query.edit_message_text(
            response_message,
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            response_message,
            reply_markup=keyboard,
        )

    return State.PABOR_INVOICE_VERIFICATION


async def invoice_verification_change_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    items = invoice.get('items')

    await query.edit_message_text(
        f"Ну давай, изменяй айтемы",
        reply_markup=await _get_items_buttons(invoice_id),
    )

    return State.PABOR_INVOICE_CHANGE_ITEMS


async def invoice_verification_change_items_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await invoice_verification(update, context)


async def _get_items_buttons(invoice_id):
    invoice = await Invoice.find_by_id(invoice_id)
    items_ids = invoice.get('items_ids', [])
    buttons = []
    for item_id in items_ids:
        item = await Item.find_by_id(item_id)
        buttons.append(
            [
                InlineKeyboardButton(item.get('name'), callback_data=f"invoice_change_item_{item_id}"),
            ],
        )
    buttons.append([InlineKeyboardButton("Готово", callback_data="ready")])

    return InlineKeyboardMarkup(buttons)


async def invoice_verification_change_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)

    try:
        item_id = re.match(Callback.INVOICE_CHANGE_ITEM, query.data).group(1)
        await BotState.edit(user_id, invoice_id, item_id)
    except (IndexError, AttributeError):
        item_id = bot_state.get('item_id')
    item = await Item.find_by_id(item_id)
    item_division = item.get('users_division', {})

    try:
        button_user_id = re.match(Callback.INVOICE_ITEM_USER, query.data).group(1)
        diff = re.match(Callback.INVOICE_ITEM_USER, query.data).group(2)
    except (IndexError, AttributeError):
        button_user_id = None
        diff = None

    if (
            diff == "minus" and
            item_division.get(button_user_id, None)
    ):
        await Item.edit_user_division(
            item_id, button_user_id, item_division[button_user_id] - 1,
        )
    elif diff == "plus":
        await Item.edit_user_division(
            item_id, button_user_id, item_division.get(button_user_id, 0) + 1,
        )

    await _recalculate_users_owe(invoice_id)

    await query.edit_message_text(
        "Измени между кем делить\n"
        f"{item.get('name')}\n{item.get('details')}\nЦена = {item.get('total_price')}?",
        reply_markup=await _get_item_buttons(
            invoice_id, item_id, cancel_button=False,
        ),
    )

    return State.PABOR_INVOICE_CHANGE_ITEM


async def invoice_verification_change_item_ready(
        update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    await BotState.edit(user_id, invoice_id)

    return await invoice_verification_change_items(update, context)


async def invoice_verification_change_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)

    paying_users = invoice.get('users_owe', {})
    users_group = invoice.get('users_group', [])

    try:
        button_user_id = re.match(Callback.INVOICE_GROUP_USER, query.data).group(1)
    except (IndexError, AttributeError):
        button_user_id = None

    if (
            button_user_id and
            button_user_id in users_group and
            button_user_id not in paying_users
    ):
        await Invoice.remove_user_from_group(invoice_id, button_user_id)
    elif button_user_id and button_user_id not in users_group:
        await Invoice.add_user_to_group(invoice_id, button_user_id)

    await query.edit_message_text(
        f"Измени список тех, кто причастен к этой покупке",
        reply_markup=await _get_group_buttons(invoice_id, back_button=False),
    )

    return State.PABOR_INVOICE_CHANGE_GROUP


async def invoice_verification_change_group_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await invoice_verification(update, context)


async def invoice_verification_change_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    name = invoice.get('name', '')

    await query.edit_message_text(
        f"Измени название покупки. Сейчас это \"{name}\". Отправь новое",
    )

    return State.PABOR_INVOICE_CHANGE_NAME


async def invoice_verification_change_name_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    await Invoice.edit_name(invoice_id, update.message.text)

    return await invoice_verification(update, context)


async def invoice_verification_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    await _send_invoice_money_requests(context, invoice_id)
    invoice = await Invoice.find_by_id(invoice_id)
    users_list = invoice.get('users_owe', {}).keys()

    await BotState.edit(user_id, invoice_id=None)
    await query.edit_message_text(
        user_id,
        f"Окей. Отправил сообщение о поборе этим придуркам: {users_list}",
    )

    return State.END


async def _send_invoice_money_requests(context: ContextTypes.DEFAULT_TYPE, invoice_id):
    invoice = await Invoice.find_by_id(invoice_id)
    users_owe = invoice.get('users_owe', {})
    owner = await User.find_by_id(invoice.get('owner_id'))

    for user_id, user_total in users_owe.items():
        if user_id == owner['id']:
            continue  # comment if you want to check it yourself

        operation_id = await Operation.create(invoice_id, user_id, user_total)
        await User.add_operation_id(user_id, operation_id)
        user = await User.find_by_id(user_id)
        user_tg_id = user.get('tg_id')
        await _send_invoice(context, user_tg_id, user_total, invoice, owner, operation_id, 'not_payed')


async def _send_invoice(context: ContextTypes.DEFAULT_TYPE, user_tg_id, user_total, invoice, owner, operation_id, operation_status):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Заплатил", callback_data=f"paid_operation_{operation_id}")]])
    if operation_status == 'not_payed':
        await context.bot.send_message(
            user_tg_id,
            f"Эй, ты должен {owner['name']} {user_total} деняк за {invoice['name']}. Скинь на его реквизиты: {owner['requisites']}",
            reply_markup=keyboard,
        )
    elif operation_status == 'verification':
        await context.bot.send_message(
            user_tg_id,
            f"Ты сказал, что скинул {owner['name']} {user_total} деняк за {invoice['name']}. Он сейчас проверяет",
        )
    elif operation_status == 'declined':
        await context.bot.send_message(
            user_tg_id,
            f"Ты сказал, что скинул {owner['name']} {user_total} деняк за {invoice['name']}, а он говорит, что ты врешь. Скинь!",
            reply_markup=keyboard,
        )
    elif operation_status == 'accepted':
        await context.bot.send_message(
            user_tg_id,
            f"Ты скинул {owner['name']} {user_total} деняк за {invoice['name']}. Красава",
        )


async def user_operation_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))

    try:
        operation_id = re.match(Callback.PAID_OPERATION, query.data).group(1)
    except (IndexError, AttributeError):
        return

    await Operation.edit_status(operation_id, status="verification")
    operation = await Operation.find_by_id(operation_id)
    invoice_id = operation.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    owner_id = invoice.get('owner_id')
    owner = await User.find_by_id(owner_id)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton('Реально скинул', callback_data=f'accept_operation_{operation_id}'),
                InlineKeyboardButton('Врет, ничего не скинул он', callback_data=f'decline_operation_{operation_id}'),
            ],
        ],
    )
    await context.bot.send_message(
        owner.get('tg_id'),
        f"Эй, {author['name']} говорит, что скинул {operation['user_total']} "
        f"деняк за {invoice['name']}. Проверь",
        reply_markup=keyboard,
    )
    await query.edit_message_text(
        f"Написал {owner['name']}, что ты скинул. Как проверит - напишу",
    )


async def user_operation_paid_declined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))

    try:
        operation_id = re.match(Callback.DECLINE_OPERATION, query.data).group(1)
    except (IndexError, AttributeError):
        return

    operation = await Operation.find_by_id(operation_id)
    invoice_id = operation.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    user = await User.find_by_id(operation.get('user_id'))

    await Operation.edit_status(operation_id, status="declined")
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton('Ну теперь реально скинул', callback_data=f'paid_operation_{operation_id}'),
            ],
        ],
    )

    await context.bot.send_message(
        user.get('tg_id'),
        f"Эй, {author['name']} говорит, что ты соврал и не скинул {operation['user_total']} "
        f"деняк за {invoice['name']}. Давай решай вопросики с ним",
        reply_markup=keyboard,
    )
    await query.edit_message_text(
        f"Ну и плохой человек. Я ему сказал скинуть заново",
    )


async def user_operation_paid_accepted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))

    try:
        operation_id = re.match(Callback.ACCEPT_OPERATION, query.data).group(1)
    except (IndexError, AttributeError):
        return

    operation = await Operation.find_by_id(operation_id)
    invoice_id = operation.get('invoice_id')
    invoice = await Invoice.find_by_id(invoice_id)
    user = await User.find_by_id(operation.get('user_id'))

    await Operation.edit_status(operation_id, status="accepted")

    await context.bot.send_message(
        user['tg_id'],
        f"Эй, {author['name']} проверил, сказал, что ты реально скинул {operation['user_total']} "
        f"деняк за {invoice['name']}. Крутой",
    )
    await query.edit_message_text(
        f"Круто",
    )


async def invoice_verification_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Да", callback_data="ready"),
                InlineKeyboardButton("Нет", callback_data="back"),
            ],
        ],
    )
    await query.edit_message_text(
        f"Уверен, что хочешь отменить чек?",
        reply_markup=keyboard,
    )

    return State.PABOR_INVOICE_CHANGE_CANCEL


async def invoice_verification_cancel_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    author = await User.find_by_tg_id(str(query.from_user.id))
    user_id = str(author.get('_id'))
    bot_state = await BotState.find_by_user_id(user_id)
    invoice_id = bot_state.get('invoice_id')
    await BotState.edit(user_id, invoice_id=None)
    await Invoice.delete(invoice_id)

    await query.edit_message_text(
        f"Весь чек поехал в помойку",
    )

    return State.END


async def invoice_verification_cancel_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await invoice_verification(update, context)


async def i_owe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    author = await User.find_by_tg_id(str(update.message.from_user.id))
    user_id = str(author.get('_id'))
    user_operations = author.get('operations_ids', [])
    await update.message.reply_text(
        f"Вот список:",
    )
    for operation_id in user_operations:
        operation = await Operation.find_by_id(operation_id)
        user_total = operation.get('user_total')
        invoice = await Invoice.find_by_id(operation.get('invoice_id'))
        owner = await User.find_by_id(invoice.get('owner_id'))
        await _send_invoice(
            context, author['tg_id'], user_total, invoice, owner, operation_id, operation['status'],
        )

# TODO: add i_owe and some other paid handlers
i_owe_handler = CommandHandler('i_owe', i_owe)
user_operation_paid_handler = CallbackQueryHandler(user_operation_paid, pattern=Callback.PAID_OPERATION)
user_operation_paid_accepted_handler = CallbackQueryHandler(user_operation_paid_accepted, pattern=Callback.ACCEPT_OPERATION)
user_operation_paid_declined_handler = CallbackQueryHandler(user_operation_paid_declined, pattern=Callback.DECLINE_OPERATION)
pabor_handler = ConversationHandler(
    entry_points=[CommandHandler("new_pabor", new_pabor)],
    states={
        State.PABOR_QR: [
            MessageHandler(filters.TEXT, qr),
            MessageHandler(filters.PHOTO, qr_photo),
            CallbackQueryHandler(qr_back, pattern=Callback.BACK),
        ],
        State.PABOR_INVOICE_GROUP: [
            CallbackQueryHandler(invoice_group, pattern=Callback.INVOICE_GROUP_USER),
            CallbackQueryHandler(invoice_group_back, pattern=Callback.BACK),
            CallbackQueryHandler(invoice_group_ready, pattern=Callback.READY),
        ],
        State.PABOR_INVOICE_ITEM: [
            CallbackQueryHandler(invoice_item, pattern=Callback.INVOICE_ITEM_USER),
            CallbackQueryHandler(invoice_item_back, pattern=Callback.BACK),
            CallbackQueryHandler(invoice_item_ready, pattern=Callback.READY),
        ],
        State.PABOR_INVOICE_NAME: [
            MessageHandler(filters.TEXT, invoice_name),
            CallbackQueryHandler(invoice_name_back, pattern=Callback.BACK),
        ],
        State.PABOR_INVOICE_VERIFICATION: [
            CallbackQueryHandler(invoice_verification_change_group, pattern=Callback.INVOICE_CHANGE_GROUP),
            CallbackQueryHandler(invoice_verification_change_items, pattern=Callback.INVOICE_CHANGE_ITEMS),
            CallbackQueryHandler(invoice_verification_change_name, pattern=Callback.INVOICE_CHANGE_NAME),
            CallbackQueryHandler(invoice_verification_cancel, pattern=Callback.BACK),
            CallbackQueryHandler(invoice_verification_ready, pattern=Callback.READY),
        ],
        State.PABOR_INVOICE_CHANGE_GROUP: [
            CallbackQueryHandler(invoice_verification_change_group, pattern=Callback.INVOICE_GROUP_USER),
            CallbackQueryHandler(invoice_verification_change_group_ready, pattern=Callback.READY),
        ],
        State.PABOR_INVOICE_CHANGE_ITEMS: [
            CallbackQueryHandler(invoice_verification_change_item, pattern=Callback.INVOICE_CHANGE_ITEM),
            CallbackQueryHandler(invoice_verification_change_items_ready, pattern=Callback.READY),
        ],
        State.PABOR_INVOICE_CHANGE_ITEM: [
            CallbackQueryHandler(invoice_verification_change_item, pattern=Callback.INVOICE_ITEM_USER),
            CallbackQueryHandler(invoice_verification_change_item_ready, pattern=Callback.READY),
        ],
        State.PABOR_INVOICE_CHANGE_NAME: [
            MessageHandler(filters.TEXT, invoice_verification_change_name_ready),
        ],
        State.PABOR_INVOICE_CHANGE_CANCEL: [
            CallbackQueryHandler(invoice_verification_cancel_no, pattern=Callback.BACK),
            CallbackQueryHandler(invoice_verification_cancel_yes, pattern=Callback.READY),
        ],
    },
    fallbacks=[CommandHandler("cancel", invoice_verification_cancel_yes)],
)

handlers = [
    i_owe_handler,
    user_operation_paid_handler,
    user_operation_paid_accepted_handler,
    user_operation_paid_declined_handler,
    pabor_handler,
]