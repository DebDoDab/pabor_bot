import os
from telegram.ext import ApplicationBuilder

from login import handlers as login_handlers
from help import handlers as help_handlers
from pabor import handlers as pabor_handlers


if __name__ == '__main__':
    application = ApplicationBuilder().token(os.getenv("TG_BOT_KEY")).build()

    handlers = []
    handlers.extend(login_handlers)
    handlers.extend(help_handlers)
    handlers.extend(pabor_handlers)

    for handler in handlers:
        application.add_handler(handler)

    application.run_polling()
