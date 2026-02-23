"""
Обработчики команд Telegram бота QR-Finder
"""
import logging
import io
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.config import BOT_USERNAME, DATABASE_PATH, QR_PACKAGES, PAYMENT_DETAILS, ADMIN_ID
from database.models import Database

logger = logging.getLogger(__name__)
db = Database(DATABASE_PATH)

STAR_MAP = {1: '1 zvezda', 2: '2 zvezdy', 3: '3 zvezdy', 4: '4 zvezdy', 5: '5 zvezd'}
STAR_EMO = {1: '\u2b50', 2: '\u2b50\u2b50', 3: '\u2b50\u2b50\u2b50', 4: '\u2b50\u2b50\u2b50\u2b50', 5: '\u2b50\u2b50\u2b50\u2b50\u2b50'}


# ─────────────────────────────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if context.args and context.args[0].startswith('found_'):
        await found_handler(update, context, context.args[0].replace('found_', ''))
        return

    is_new = not db.user_exists(user.id)
    if is_new:
        db.create_user(user.id, user.username or '', user.full_name)

    greeting = "Dobro pozhalovat' v" if is_new else "S vozvrashcheniem v"
    mark = "\U0001f389 " if is_new else "\U0001f44b "

    lines = [
        f"{mark}{user.first_name}!",
        "",
        f"{'Vy zaregistrirovany v' if is_new else 'S vozvrashcheniem v'} QR-Finder.",
        "",
        "Kak eto rabotaet:",
        "1\ufe0f\u20e3 Kupite QR-kod /buy",
        "2\ufe0f\u20e3 Poluchite unikal'nyj QR-kod",
        "3\ufe0f\u20e3 Raspechatajte i naklejte na veshch'",
        "4\ufe0f\u20e3 Esli veshch' najdut \u2014 pridet uvedomlenie s kontaktom nashedshego",
        "",
        "/buy \u2014 kupit' QR-kod",
        "/myitems \u2014 moi QR-kody",
        "/history \u2014 istoriya",
        "/review \u2014 ostavit' otzyv",
        "/help \u2014 pomoshch'",
    ]

    # We'll write the actual Russian text directly in a separate approach
    text = (
        f"{'🎉 ' if is_new else '👋 '}{user.first_name}!\n\n"
        f"{'Добро пожаловать в' if is_new else 'С возвращением в'} QR-Finder.\n\n"
        "Как это работает:\n"
        "1️⃣ Купите QR-код /buy\n"
        "2️⃣ Получите уникальный QR-код\n"
        "3️⃣ Распечатайте и наклейте на вещь\n"
        "4️⃣ Если вещь найдут — придёт уведомление с контактом нашедшего\n\n"
        "/buy — купить QR-код\n"
        "/myitems — мои QR-коды\n"
        "/history — история\n"
        "/review — оставить отзыв\n"
        "/help — помощь"
    )
    keyboard = [
        [InlineKeyboardButton("🛒 Купить QR-код",      callback_data='packages')],
        [InlineKeyboardButton("📋 Мои QR-коды",        callback_data='my_items')],
        [InlineKeyboardButton("ℹ️ Как это работает?", callback_data='how_it_works')],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────────────────────────────
# /buy
# ─────────────────────────────────────────────────────────────────────

async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.user_exists(user_id):
        await update.message.reply_text("Сначала запустите бот: /start")
        return
    await _show_packages_menu(update.message, user_id, edit=False)


async def _show_packages_menu(message, user_id: int, edit: bool = False):
    pkg = db.get_active_package(user_id)
    if pkg:
        qr_status   = "✅ QR создан" if pkg.get('qr_used') else "⚡ QR ещё не создан"
        status_line = f"Текущий QR-код активен до {pkg['expires_at'][:10]} | {qr_status}\n\n"
    else:
        status_line = "У вас нет активного QR-кода.\n\n"

    text = (
        "🛒 Купить QR-код — QR-Finder\n\n"
        f"{status_line}"
        "Каждый пакет включает 1 QR-код на весь срок.\n"
        "QR перестаёт работать после истечения срока.\n\n"
        "🥉 1 месяц — 300 тг\n"
        "🥈 3 месяца — 700 тг\n"
        "🥇 6 месяцев — 1200 тг"
    )
    keyboard = [
        [InlineKeyboardButton("🥉 1 месяц — 300 тг",    callback_data='buy:month_1')],
        [InlineKeyboardButton("🥈 3 месяца — 700 тг",   callback_data='buy:month_3')],
        [InlineKeyboardButton("🥇 6 месяцев — 1200 тг", callback_data='buy:month_6')],
    ]
    if edit:
        try:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        except Exception:
            pass
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def _handle_buy_plan(query, user_id: int, plan_key: str):
    plan = QR_PACKAGES.get(plan_key)
    if not plan:
        await query.answer("Неизвестный пакет", show_alert=True)
        return

    text = (
        f"{plan['emoji']} {plan['label']}\n\n"
        f"Сумма: {plan['price']} тг\n\n"
        f"Реквизиты:\n{PAYMENT_DETAILS}\n\n"
        f"Комментарий к переводу:\nQR {plan_key} | ID: {user_id}\n\n"
        "После перевода нажмите «Я оплатил» — активируем QR-код в течение нескольких минут."
    )
    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил",        callback_data=f"paid:{plan_key}")],
        [InlineKeyboardButton("◀️ Назад к пакетам",  callback_data='packages')],
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────────────────────────────
# Создание QR
# ─────────────────────────────────────────────────────────────────────

async def additem_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.user_exists(user_id):
        await update.message.reply_text("Сначала запустите бот: /start")
        return
    await _create_qr_for_user(update.message, context, user_id, edit=False)


async def _create_qr_for_user(message, context, user_id: int, edit: bool = False):
    pkg = db.get_active_package(user_id)

    if not pkg:
        text = (
            "⛔ Сначала купите QR-код.\n\n"
            "🥉 1 месяц — 300 тг\n"
            "🥈 3 месяца — 500 тг\n"
            "🥇 6 месяцев — 1000 тг"
        )
        keyboard = [[InlineKeyboardButton("🛒 Купить QR-код", callback_data='packages')]]
        if edit:
            try:
                await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                return
            except Exception:
                pass
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if pkg.get('qr_used'):
        items  = db.get_user_items(user_id)
        active = next(
            (i for i in items if i.get('expires_at', '') >= datetime.now().strftime('%Y-%m-%d')),
            None
        )
        if active:
            text = (
                "ℹ️ QR-код в этом пакете уже создан.\n\n"
                f"🏷 Ваш QR: {active['qr_id']}\n"
                f"⏳ Активен до: {active['expires_at'][:10]}\n\n"
                "Для нового QR-кода купите новый пакет."
            )
            keyboard = [
                [InlineKeyboardButton("🖼 Получить QR-изображение", callback_data=f"send_qr:{active['qr_id']}")],
                [InlineKeyboardButton("🛒 Купить новый пакет",       callback_data='packages')],
            ]
            if edit:
                try:
                    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                    return
                except Exception:
                    pass
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

    item = db.create_item(user_id, expires_at=pkg['expires_at'])
    if not item:
        await message.reply_text("❌ Ошибка при создании QR-кода. Попробуйте ещё раз.")
        return

    db.mark_qr_used(user_id)

    qr_id    = item['qr_id']
    qr_image = db.generate_qr_image(qr_id, BOT_USERNAME)
    qr_url   = f"https://t.me/{BOT_USERNAME}?start=found_{qr_id}"

    caption = (
        f"✅ QR-код создан!\n\n"
        f"🏷 Код: {qr_id}\n"
        f"⏳ Активен до: {pkg['expires_at'][:10]}\n\n"
        "Распечатайте и наклейте на вещь.\n"
        "Когда кто-то отсканирует — вы получите уведомление с контактом нашедшего.\n\n"
        f"🔗 Ссылка: {qr_url}"
    )
    keyboard = [[InlineKeyboardButton("📋 Мои QR-коды", callback_data='my_items')]]
    await message.reply_photo(
        photo=io.BytesIO(qr_image),
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─────────────────────────────────────────────────────────────────────
# /myitems
# ─────────────────────────────────────────────────────────────────────

def _build_items_text(items: list, user_id: int) -> tuple:
    pkg = db.get_active_package(user_id)
    pkg_line = (
        f"✅ QR-код активен до {pkg['expires_at'][:10]}"
        if pkg else "❌ Нет активного QR-кода"
    )

    if not items:
        text = f"📋 Мои QR-коды\n\n{pkg_line}\n\nQR-кодов пока нет."
        keyboard = [
            [InlineKeyboardButton("⚡ Создать QR-код", callback_data='add_item')],
            [InlineKeyboardButton("🛒 Купить пакет",   callback_data='packages')],
        ]
        return text, InlineKeyboardMarkup(keyboard)

    text = f"📋 Мои QR-коды ({len(items)})\n{pkg_line}\n{'─' * 30}\n\n"
    for i, item in enumerate(items, 1):
        scanned = f"  · отсканирован {item['times_found']} раз" if item['times_found'] > 0 else ""
        exp     = f"\n   ⏳ до {item['expires_at'][:10]}" if item.get('expires_at') else ""
        text   += f"{i}. 🏷 {item['qr_id']}{scanned}{exp}\n   Создан: {item['added_at'][:10]}\n\n"

    keyboard = [
        [InlineKeyboardButton(f"🏷 {item['qr_id']}", callback_data=f"item_qr:{item['qr_id']}")]
        for item in items
    ]
    keyboard.append([
        InlineKeyboardButton("⚡ Создать QR-код", callback_data='add_item'),
        InlineKeyboardButton("🛒 Купить пакет",   callback_data='packages'),
    ])
    return text, InlineKeyboardMarkup(keyboard)


async def myitems_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        message = update.callback_query.message
        edit    = True
    else:
        user_id = update.effective_user.id
        message = update.message
        edit    = False

    if not db.user_exists(user_id):
        await message.reply_text("Сначала запустите бот: /start")
        return

    items = db.get_user_items(user_id)
    text, markup = _build_items_text(items, user_id)
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
            return
        except Exception:
            pass
    await message.reply_text(text, reply_markup=markup)


# ─────────────────────────────────────────────────────────────────────
# /history
# ─────────────────────────────────────────────────────────────────────

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not db.user_exists(user_id):
        await update.message.reply_text("Сначала запустите бот: /start")
        return

    my_findings = db.get_user_findings(user_id, as_owner=True)
    found_by_me = db.get_user_findings(user_id, as_owner=False)

    text = "📜 История сканирований\n\n"

    if my_findings:
        text += "🔍 Мои QR-коды отсканировали:\n"
        for f in my_findings[:5]:
            finder = f['finder_name']
            if f.get('finder_username'):
                finder += f" (@{f['finder_username']})"
            text += f"\n🏷 {f['qr_id']}\n   Нашёл: {finder}\n   Когда: {f['found_at'][:16]}\n"
    else:
        text += "🔍 Мои QR-коды ещё не сканировали.\n"

    text += "\n"

    if found_by_me:
        text += "🤝 Я отсканировал чужие QR:\n"
        for f in found_by_me[:5]:
            text += f"\n🏷 {f['qr_id']}  {f['found_at'][:16]}\n"
    else:
        text += "🤝 Я ещё не сканировал чужие QR."

    keyboard = [[InlineKeyboardButton("📋 Мои QR-коды", callback_data='my_items')]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────────────────────────────
# /review
# ─────────────────────────────────────────────────────────────────────

async def review_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id   = update.effective_user.id
    full_name = update.effective_user.full_name

    if not db.user_exists(user_id):
        await update.message.reply_text("Сначала запустите бот: /start")
        return

    if context.args:
        try:
            rating = int(context.args[0])
            if not 1 <= rating <= 5:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Укажите оценку от 1 до 5.\n\nПример: /review 5 Отличный сервис!"
            )
            return

        review_text = ' '.join(context.args[1:]).strip()

        if db.add_review(user_id, full_name, rating, review_text):
            stars = STAR_EMO[rating]
            await update.message.reply_text(
                f"✅ Спасибо за отзыв!\n\n{stars} — {review_text or '(без комментария)'}"
            )
            if ADMIN_ID:
                try:
                    uname = update.effective_user.username
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=(
                            f"⭐ Новый отзыв\n\n"
                            f"От: {full_name}" + (f" (@{uname})" if uname else "") +
                            f"\nОценка: {stars}\nТекст: {review_text or '—'}"
                        )
                    )
                except Exception:
                    pass
        else:
            await update.message.reply_text("❌ Не удалось сохранить. Попробуйте ещё раз.")
        return

    text = (
        "⭐ Оставить отзыв о QR-Finder\n\n"
        "Выберите оценку:\n\n"
        "Или напишите сразу:\n/review 5 Всё супер, вещь нашлась быстро!"
    )
    keyboard = [
        [
            InlineKeyboardButton("1 ⭐",       callback_data='review:1'),
            InlineKeyboardButton("2 ⭐⭐",     callback_data='review:2'),
            InlineKeyboardButton("3 ⭐⭐⭐",   callback_data='review:3'),
        ],
        [
            InlineKeyboardButton("4 ⭐⭐⭐⭐",   callback_data='review:4'),
            InlineKeyboardButton("5 ⭐⭐⭐⭐⭐", callback_data='review:5'),
        ],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────────────────────────────
# /stats
# ─────────────────────────────────────────────────────────────────────

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = db.get_statistics()
    rating_line = (
        f"⭐ Средняя оценка: {s['avg_rating']} ({s['total_reviews']} отзывов)\n"
        if s['total_reviews'] else ""
    )
    text = (
        "📊 Статистика QR-Finder\n\n"
        f"👥 Пользователей: {s['total_users']}\n"
        f"🏷 QR-кодов выдано: {s['total_items']}\n"
        f"🔍 Сканирований: {s['total_findings']}\n"
        + rating_line
    )
    keyboard = [[InlineKeyboardButton("📋 Мои QR-коды", callback_data='my_items')]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────────────────────────────
# /help
# ─────────────────────────────────────────────────────────────────────

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 Команды QR-Finder\n\n"
        "/start    — главное меню\n"
        "/buy      — купить QR-код\n"
        "/myitems  — мои QR-коды\n"
        "/history  — история сканирований\n"
        "/review   — оставить отзыв\n"
        "/stats    — статистика\n"
        "/help     — эта справка\n\n"
        "Как начать:\n"
        "1. /buy — выберите пакет и оплатите\n"
        "2. Администратор активирует QR-код\n"
        "3. Зайдите в /myitems и создайте QR\n"
        "4. Распечатайте и наклейте на вещь"
    )
    keyboard = [
        [InlineKeyboardButton("🛒 Купить QR-код",      callback_data='packages')],
        [InlineKeyboardButton("ℹ️ Как это работает?", callback_data='how_it_works')],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────────────────────────────
# /delete
# ─────────────────────────────────────────────────────────────────────

async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🗑️ Для удаления QR-кода перейдите в /myitems и нажмите на нужный код."
    )


# Заглушки удалённых команд
async def achievements_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Эта функция недоступна.")

async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Эта функция недоступна.")


# ─────────────────────────────────────────────────────────────────────
# Обработчик текста
# ─────────────────────────────────────────────────────────────────────

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if context.user_data.get('awaiting_review_rating'):
        rating      = context.user_data.pop('awaiting_review_rating')
        full_name   = update.effective_user.full_name
        text_in     = update.message.text.strip()
        review_text = '' if text_in == '-' else text_in

        if db.add_review(user_id, full_name, rating, review_text):
            stars = STAR_EMO[rating]
            await update.message.reply_text(
                f"✅ Отзыв сохранён!\n\n{stars} — {review_text or '(без комментария)'}"
            )
            if ADMIN_ID:
                try:
                    uname = update.effective_user.username
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=(
                            f"⭐ Новый отзыв\n\nОт: {full_name}"
                            + (f" (@{uname})" if uname else "")
                            + f"\nОценка: {stars}\nТекст: {review_text or '—'}"
                        )
                    )
                except Exception:
                    pass
        else:
            await update.message.reply_text("❌ Ошибка. Попробуйте /review ещё раз.")
        return

    if not db.user_exists(user_id):
        await update.message.reply_text("Сначала запустите бот: /start")
        return

    await update.message.reply_text(
        "Используйте команды:\n"
        "/buy — купить QR-код\n"
        "/myitems — мои QR-коды\n"
        "/review — оставить отзыв\n"
        "/help — все команды"
    )


# ─────────────────────────────────────────────────────────────────────
# found_handler
# ─────────────────────────────────────────────────────────────────────

async def found_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, qr_id: str):
    finder          = update.effective_user
    finder_id       = finder.id
    finder_name     = finder.full_name
    finder_username = finder.username or ''

    if not db.user_exists(finder_id):
        db.create_user(finder_id, finder_username, finder_name)

    item = db.get_item_by_qr(qr_id)
    if not item:
        await update.message.reply_text(
            "❌ QR-код не найден или срок действия истёк.\n\n"
            f"Зарегистрируйте свои вещи в @{BOT_USERNAME}"
        )
        return

    if item.get('expires_at'):
        if datetime.now().strftime('%Y-%m-%d %H:%M:%S') > item['expires_at']:
            await update.message.reply_text(
                "⏰ Срок действия этого QR-кода истёк.\n"
                "Владелец не продлил пакет."
            )
            return

    owner_id = item['user_id']
    if owner_id == finder_id:
        await update.message.reply_text(f"😊 Это ваш QR-код ({qr_id}).")
        return

    db.create_finding(qr_id, owner_id, finder_id, finder_name, finder_username)

    finder_keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu')]]
    await update.message.reply_text(
        "✅ Спасибо за честность!\n\n"
        "Владелец уже получил уведомление с вашим контактом и свяжется с вами. 🤝",
        reply_markup=InlineKeyboardMarkup(finder_keyboard)
    )

    try:
        if finder_username:
            contact_url   = f"https://t.me/{finder_username}"
            contact_label = f"💬 Написать @{finder_username}"
        else:
            contact_url   = f"tg://user?id={finder_id}"
            contact_label = f"💬 Написать {finder_name}"

        owner_text = (
            f"🎉 Ваш QR-код отсканировали!\n\n"
            f"🏷 QR: {qr_id}\n"
            f"👤 Нашёл: {finder_name}"
            + (f" (@{finder_username})" if finder_username else "")
            + f"\n⏰ {datetime.now().strftime('%H:%M, %d.%m.%Y')}\n\n"
            "Нажмите кнопку чтобы написать нашедшему 👇"
        )
        if not finder_username:
            owner_text += f"\n\n⚠️ У нашедшего нет @username. Найдите по имени: {finder_name}"

        keyboard = [
            [InlineKeyboardButton(contact_label, url=contact_url)],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu')],
        ]
        await context.bot.send_message(
            chat_id=owner_id,
            text=owner_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления владельца: {e}")


# ─────────────────────────────────────────────────────────────────────
# button_handler
# ─────────────────────────────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    data = query.data

    async def edit_or_send(text, markup=None, **kwargs):
        try:
            await query.message.edit_text(text, reply_markup=markup, **kwargs)
        except Exception:
            await query.message.reply_text(text, reply_markup=markup, **kwargs)

    # ── Пакеты ────────────────────────────────────────────────────────
    if data in ('packages', 'subscription'):
        await _show_packages_menu(query.message, user_id, edit=True)

    elif data.startswith('buy:'):
        await _handle_buy_plan(query, user_id, data.split(':', 1)[1])

    elif data.startswith('paid:'):
        plan_key = data.split(':', 1)[1]
        plan     = QR_PACKAGES.get(plan_key)
        if not plan:
            await query.answer("Неизвестный пакет", show_alert=True)
            return

        db.add_pending_payment(user_id, plan_key)

        if ADMIN_ID:
            try:
                user  = db.get_user(user_id)
                name  = user['full_name'] if user else str(user_id)
                uname = user.get('username', '') if user else ''
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        f"💳 Новая оплата!\n\n"
                        f"Пользователь: {name}" + (f" (@{uname})" if uname else "") +
                        f"\nID: {user_id}\nПакет: {plan['label']}\n\n"
                        f"Активировать:\n/activate {user_id} {plan_key}"
                    )
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления администратора: {e}")

        await edit_or_send(
            "✅ Заявка отправлена!\n\n"
            f"Пакет: {plan['label']}\n\n"
            "Администратор проверит платёж и активирует QR-код в течение нескольких минут.\n"
            "Если через 30 минут ничего — напишите администратору напрямую.",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data='back_to_menu')]])
        )

    # ── Создать QR ────────────────────────────────────────────────────
    elif data == 'add_item':
        await _create_qr_for_user(query.message, context, user_id, edit=True)

    # ── Мои QR ────────────────────────────────────────────────────────
    elif data == 'my_items':
        if not db.user_exists(user_id):
            await edit_or_send("Сначала запустите бот: /start")
            return
        items = db.get_user_items(user_id)
        text, markup = _build_items_text(items, user_id)
        await edit_or_send(text, markup)

    # ── Конкретный QR ─────────────────────────────────────────────────
    elif data.startswith('item_qr:'):
        qr_id = data.split(':', 1)[1]
        item  = db.get_item_by_qr(qr_id)
        if not item:
            await query.answer("QR-код не найден", show_alert=True)
            return
        qr_url  = f"https://t.me/{BOT_USERNAME}?start=found_{qr_id}"
        scanned = f"\n🔍 Отсканирован {item['times_found']} раз" if item['times_found'] > 0 else ""
        exp     = f"\n⏳ Активен до: {item['expires_at'][:10]}" if item.get('expires_at') else ""
        text    = (
            f"🏷 QR-код: {qr_id}\n{'─' * 30}\n\n"
            f"📅 Создан: {item['added_at'][:10]}{scanned}{exp}\n\n"
            f"Ссылка:\n{qr_url}"
        )
        keyboard = [
            [InlineKeyboardButton("🖼 Получить QR-изображение", callback_data=f"send_qr:{qr_id}")],
            [InlineKeyboardButton("🗑️ Удалить",                 callback_data=f"confirm_delete:{qr_id}")],
            [InlineKeyboardButton("◀️ Назад",                   callback_data='my_items')],
        ]
        await edit_or_send(text, InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)

    # ── QR-изображение ────────────────────────────────────────────────
    elif data.startswith('send_qr:'):
        qr_id = data.split(':', 1)[1]
        item  = db.get_item_by_qr(qr_id)
        if not item:
            await query.answer("QR-код не найден", show_alert=True)
            return
        qr_image = db.generate_qr_image(qr_id, BOT_USERNAME)
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=io.BytesIO(qr_image),
            caption=(
                f"🏷 {qr_id}"
                + (f"\n⏳ Активен до: {item['expires_at'][:10]}" if item.get('expires_at') else "")
            )
        )

    # ── Удаление ──────────────────────────────────────────────────────
    elif data.startswith('confirm_delete:'):
        qr_id = data.split(':', 1)[1]
        if not db.get_item_by_qr(qr_id):
            await query.answer("QR-код не найден", show_alert=True)
            return
        keyboard = [
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"do_delete:{qr_id}")],
            [InlineKeyboardButton("❌ Отмена",      callback_data=f"item_qr:{qr_id}")],
        ]
        await edit_or_send(
            f"🗑️ Удалить QR-код {qr_id}?\n\nЭто действие нельзя отменить.",
            InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith('do_delete:'):
        qr_id   = data.split(':', 1)[1]
        success = db.delete_item(qr_id, user_id)
        await query.answer("✅ Удалено" if success else "❌ Ошибка")
        items = db.get_user_items(user_id)
        text, markup = _build_items_text(items, user_id)
        await edit_or_send(text, markup)

    # ── Отзыв через кнопки ────────────────────────────────────────────
    elif data.startswith('review:'):
        rating = int(data.split(':', 1)[1])
        stars  = STAR_EMO[rating]
        context.user_data['awaiting_review_rating'] = rating
        await edit_or_send(
            f"Вы выбрали: {stars}\n\n"
            "Напишите комментарий к отзыву.\n"
            "Если без комментария — отправьте «-»"
        )

    # ── Как это работает ──────────────────────────────────────────────
    elif data == 'how_it_works':
        text = (
            "ℹ️ Как работает QR-Finder?\n\n"
            "Для владельца:\n"
            "1️⃣ Купите пакет — /buy\n"
            "2️⃣ Создайте QR-код в /myitems\n"
            "3️⃣ Распечатайте и наклейте на вещь\n"
            "4️⃣ Если кто-то найдёт — получите уведомление с контактом\n\n"
            "Для нашедшего:\n"
            "1️⃣ Сканирует QR камерой телефона\n"
            "2️⃣ Открывается этот бот\n"
            "3️⃣ Владелец получает ваш контакт\n\n"
            "🔒 Номер телефона владельца скрыт\n"
            "⏳ QR активен только пока действует пакет"
        )
        keyboard = [
            [InlineKeyboardButton("🛒 Купить QR-код", callback_data='packages')],
            [InlineKeyboardButton("◀️ Назад",         callback_data='back_to_menu')],
        ]
        await edit_or_send(text, InlineKeyboardMarkup(keyboard))

    # ── Статистика ────────────────────────────────────────────────────
    elif data == 'stats':
        s = db.get_statistics()
        rating_line = (
            f"⭐ Средняя оценка: {s['avg_rating']} ({s['total_reviews']} отзывов)\n"
            if s['total_reviews'] else ""
        )
        text = (
            "📊 Статистика QR-Finder\n\n"
            f"👥 Пользователей: {s['total_users']}\n"
            f"🏷 QR-кодов: {s['total_items']}\n"
            f"🔍 Сканирований: {s['total_findings']}\n"
            + rating_line
        )
        await edit_or_send(
            text,
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]])
        )

    # ── Главное меню ──────────────────────────────────────────────────
    elif data == 'back_to_menu':
        text = (
            "👋 QR-Finder — главное меню\n\n"
            "/buy — купить QR-код\n"
            "/myitems — мои QR-коды\n"
            "/history — история\n"
            "/review — оставить отзыв\n"
            "/help — все команды"
        )
        keyboard = [
            [InlineKeyboardButton("🛒 Купить QR-код",      callback_data='packages')],
            [InlineKeyboardButton("📋 Мои QR-коды",        callback_data='my_items')],
            [InlineKeyboardButton("ℹ️ Как это работает?", callback_data='how_it_works')],
        ]
        await edit_or_send(text, InlineKeyboardMarkup(keyboard))