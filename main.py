"""
Основной модуль Telegram бота QR-Finder
"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config.config import TELEGRAM_BOT_TOKEN, DATABASE_PATH, QR_PACKAGES, ADMIN_ID
from database.models import Database
from bot.handlers import (
    start_handler,
    additem_handler,
    myitems_handler,
    stats_handler,
    help_handler,
    message_handler,
    button_handler,
    delete_handler,
    history_handler,
    achievements_handler,
    review_handler,
    leaderboard_handler,
    buy_handler,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database(DATABASE_PATH)


async def activate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/activate <user_id> <plan> — активировать подписку"""
    caller_id = update.effective_user.id
    if ADMIN_ID and caller_id != ADMIN_ID:
        await update.message.reply_text("❌ Только для администратора.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            f"Использование: /activate <user_id> <plan>\n"
            f"Планы: {', '.join(QR_PACKAGES.keys())}"
        )
        return

    try:
        target_id = int(context.args[0])
        plan_key  = context.args[1]
    except ValueError:
        await update.message.reply_text("❌ user_id должен быть числом.")
        return

    plan = QR_PACKAGES.get(plan_key)
    if not plan:
        await update.message.reply_text(f"❌ Неизвестный план: {plan_key}")
        return

    if not db.user_exists(target_id):
        await update.message.reply_text(f"❌ Пользователь {target_id} не найден.")
        return

    sub = db.create_subscription(target_id, plan_key, plan['days'])

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"🎉 QR-код активирован!\n\n"
                f"{plan['emoji']} {plan['label']}\n"
                f"✅ Действует до: {sub['expires_at'][:10]}\n\n"
                f"Теперь создайте свой QR-код — нажмите /myitems или кнопку ниже."
            )
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить {target_id}: {e}")

    await update.message.reply_text(
        f"✅ QR-код активирован!\n"
        f"Пользователь: {target_id}\n"
        f"Пакет: {plan['label']}\n"
        f"До: {sub['expires_at'][:10]}"
    )


async def pending_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pending — список ожидающих платежей"""
    caller_id = update.effective_user.id
    if ADMIN_ID and caller_id != ADMIN_ID:
        await update.message.reply_text("❌ Только для администратора.")
        return

    payments = db.get_pending_payments()
    if not payments:
        await update.message.reply_text("Нет ожидающих платежей.")
        return

    text = "💳 Ожидают подтверждения:\n\n"
    for p in payments:
        plan = QR_PACKAGES.get(p['plan'], {})
        uname = f" (@{p['username']})" if p.get('username') else ""
        text += (
            f"#{p['id']} | {p['full_name']}{uname} (ID: {p['user_id']})\n"
            f"Пакет: {plan.get('label', p['plan'])}\n"
            f"Когда: {p['created_at'][:16]}\n"
            f"➡️ /activate {p['user_id']} {p['plan']}\n\n"
        )
    await update.message.reply_text(text)


class QRFinderBot:
    def __init__(self, token: str):
        self.token       = token
        self.application = None

    def setup_handlers(self):
        app = self.application
        app.add_handler(CommandHandler("start",        start_handler))
        app.add_handler(CommandHandler("buy",          buy_handler))
        app.add_handler(CommandHandler("additem",      additem_handler))
        app.add_handler(CommandHandler("myitems",      myitems_handler))
        app.add_handler(CommandHandler("stats",        stats_handler))
        app.add_handler(CommandHandler("help",         help_handler))
        app.add_handler(CommandHandler("delete",       delete_handler))
        app.add_handler(CommandHandler("history",      history_handler))
        app.add_handler(CommandHandler("achievements", achievements_handler))
        app.add_handler(CommandHandler("review",       review_handler))
        app.add_handler(CommandHandler("leaderboard",  leaderboard_handler))
        app.add_handler(CommandHandler("activate",     activate_handler))
        app.add_handler(CommandHandler("pending",      pending_handler))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        logger.info("Обработчики настроены")

    def run(self):
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN не установлен!")
            return
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()
        logger.info("🚀 QR-Finder бот запущен!")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    QRFinderBot(TELEGRAM_BOT_TOKEN).run()


if __name__ == '__main__':
    main()
