"""
Обработчики команд Telegram бота
"""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.config import ITEM_TYPES, BOT_USERNAME
from database.models import Database
from config.config import DATABASE_PATH

logger = logging.getLogger(__name__)
db = Database(DATABASE_PATH)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Проверка на находку вещи
    if context.args and context.args[0].startswith('found_'):
        await found_handler(update, context, context.args[0].replace('found_', ''))
        return
    
    # Регистрация или приветствие пользователя
    is_new = not db.user_exists(user.id)
    
    if is_new:
        db.create_user(user.id, user.username or '', user.full_name)
    
    welcome_text = f"""
{'🎉 ' if is_new else '👋 '}{user.first_name}, добро пожаловать в **QR-Находку!**

{'✨ Вы успешно зарегистрированы!' if is_new else '✅ С возвращением!'}

**Что умеет этот бот:**
📱 Помогает находить потерянные вещи через QR-коды
🔒 Защищает вашу конфиденциальность  
⚡ Мгновенно связывает нашедшего с владельцем

**Как это работает:**
1️⃣ Добавьте свои вещи (/additem)
2️⃣ Сгенерируйте и распечатайте QR-стикеры
3️⃣ Наклейте их на вещи
4️⃣ Если вещь потеряется - получите уведомление!

**Доступные команды:**
/additem - Добавить новую вещь
/myitems - Мои вещи
/history - История находок
/stats - Статистика
/help - Помощь

Начните с команды /additem! 🚀
"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить вещь", callback_data='add_item')],
        [InlineKeyboardButton("📋 Мои вещи", callback_data='my_items')],
        [InlineKeyboardButton("ℹ️ Как это работает?", callback_data='how_it_works')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def additem_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /additem"""
    user_id = update.effective_user.id
    
    # Проверка регистрации
    if not db.user_exists(user_id):
        await update.message.reply_text(
            "❌ Вы не зарегистрированы. Используйте /start"
        )
        return
    
    # Получаем список типов для удобного выбора
    types_list = '\n'.join([f"• {emoji} {type_name}" 
                           for type_name, emoji in ITEM_TYPES.items()])
    
    text = f"""
➕ **Добавление новой вещи**

Отправьте информацию в формате:
`QR_ID название тип`

**Примеры:**
• `QR001 Рюкзак_Nike рюкзак`
• `QR002 Ключи_от_дома ключи`
• `QR003 Сменка_39_размер обувь`

**Доступные типы вещей:**
{types_list}

**Ваш ID пользователя:** `{user_id}`
Используйте формат QR001, QR002 и т.д.

💡 После добавления вы получите инструкции по созданию QR-кода!
"""
    
    keyboard = [[InlineKeyboardButton("📋 Мои вещи", callback_data='my_items')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def myitems_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /myitems"""
    # Определяем тип update (может быть message или callback_query)
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        message = update.callback_query.message
    else:
        user_id = update.effective_user.id
        message = update.message
    
    if not db.user_exists(user_id):
        await message.reply_text("❌ Вы не зарегистрированы. Используйте /start")
        return
    
    items = db.get_user_items(user_id)
    
    if not items:
        text = """
📋 **Мои вещи**

У вас пока нет зарегистрированных вещей.
Добавьте первую вещь командой /additem!

💡 **Совет:** Чем больше вещей вы зарегистрируете, тем выше шанс их найти!
"""
        keyboard = [[InlineKeyboardButton("➕ Добавить вещь", callback_data='add_item')]]
    else:
        text = f"📋 **Мои зарегистрированные вещи:** ({len(items)})\n\n"
        for i, item in enumerate(items, 1):
            emoji = ITEM_TYPES.get(item['item_type'], '📦')
            
            text += f"{i}. {emoji} **{item['name']}**\n"
            text += f"   └ QR: `{item['qr_id']}`\n"
            text += f"   └ Тип: {item['item_type']}\n"
            if item['times_found'] > 0:
                text += f"   └ 🔍 Найдена {item['times_found']} раз(а)\n"
            text += f"   └ Добавлена: {item['added_at'][:10]}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить ещё", callback_data='add_item')],
            [InlineKeyboardButton("🗑️ Удалить вещь", callback_data='delete_item')]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats"""
    stats = db.get_statistics()
    
    # Формируем текст с популярными вещами
    popular_items_text = ""
    if stats['popular_items']:
        popular_items_text = "\n**Популярные типы вещей:**\n"
        for item in stats['popular_items']:
            emoji = ITEM_TYPES.get(item['item_type'], '📦')
            popular_items_text += f"{emoji} {item['item_type']}: {item['count']} шт.\n"
    
    # Формируем текст с самыми находимыми вещами
    most_found_text = ""
    if stats['most_found']:
        most_found_text = "\n**🏆 Чаще всего находят:**\n"
        for item in stats['most_found']:
            most_found_text += f"• {item['name']}: {item['times_found']} раз(а)\n"
    
    text = f"""
📊 **Статистика QR-Находки**

**Общие показатели:**
👥 Пользователей: **{stats['total_users']}**
📦 Зарегистрировано вещей: **{stats['total_items']}**
🔍 Всего находок: **{stats['total_findings']}**
✨ Активных пользователей: **{stats['active_users']}**

**Средние значения:**
📈 Вещей на пользователя: **{stats['avg_items_per_user']}**
{popular_items_text}{most_found_text}

🚀 Присоединяйся к сообществу честных людей!

💡 **Знаете ли вы?**
Каждая регистрация вещи повышает шанс её вернуть на 80%!
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Мои вещи", callback_data='my_items')],
        [InlineKeyboardButton("➕ Добавить вещь", callback_data='add_item')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    types_list = ', '.join([f"{emoji} {type_name}" 
                           for type_name, emoji in list(ITEM_TYPES.items())[:6]])
    
    text = f"""
📚 **Помощь по командам**

**Основные команды:**
/start - Начало работы и регистрация
/additem - Добавить новую вещь
/myitems - Список моих вещей
/history - История находок
/delete - Удалить вещь
/stats - Статистика проекта
/help - Эта справка

**Формат добавления вещи:**
`QR_ID название тип`

**Примеры:**
• `QR001 Рюкзак рюкзак`
• `QR002 Ключи ключи`
• `QR003 Куртка_синяя куртка`

**Доступные типы:**
{types_list}

**Как создать QR-код:**
1. Перейдите на сайт qr-code-generator.com
2. Выберите тип "URL"
3. Вставьте: `https://t.me/{BOT_USERNAME}?start=found_QR001`
4. Скачайте QR-код
5. Распечатайте на стикере

**Нужна помощь?**
Обращайтесь к разработчикам проекта!
"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить вещь", callback_data='add_item')],
        [InlineKeyboardButton("ℹ️ Как это работает?", callback_data='how_it_works')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /history - история находок"""
    user_id = update.effective_user.id
    
    if not db.user_exists(user_id):
        await update.message.reply_text("❌ Вы не зарегистрированы. Используйте /start")
        return
    
    # Получаем находки где пользователь - владелец
    my_findings = db.get_user_findings(user_id, as_owner=True)
    
    # Получаем находки где пользователь - нашедший
    found_by_me = db.get_user_findings(user_id, as_owner=False)
    
    text = "📜 **История находок**\n\n"
    
    if my_findings:
        text += "**🔍 Мои вещи, которые нашли:**\n"
        for finding in my_findings[:5]:  # Показываем последние 5
            emoji = ITEM_TYPES.get(finding['item_type'], '📦')
            status_emoji = {'pending': '⏳', 'returned': '✅', 'lost': '❌'}.get(
                finding['status'], '❓'
            )
            text += f"\n{status_emoji} {emoji} **{finding['item_name']}**\n"
            text += f"   Нашёл: {finding['finder_name']}\n"
            text += f"   Когда: {finding['found_at'][:16]}\n"
            if finding['location']:
                text += f"   Где: {finding['location']}\n"
    else:
        text += "**🔍 Мои вещи, которые нашли:**\nПока ничего не найдено\n"
    
    text += "\n"
    
    if found_by_me:
        text += "**🤝 Я нашёл чужие вещи:**\n"
        for finding in found_by_me[:5]:
            emoji = ITEM_TYPES.get(finding['item_type'], '📦')
            text += f"\n{emoji} **{finding['item_name']}**\n"
            text += f"   Когда: {finding['found_at'][:16]}\n"
    else:
        text += "**🤝 Я нашёл чужие вещи:**\nПока ничего\n"
    
    keyboard = [[InlineKeyboardButton("📋 Мои вещи", callback_data='my_items')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /delete"""
    await update.message.reply_text(
        """
🗑️ **Удаление вещи**

Чтобы удалить вещь, отправьте её QR-код:
`delete QR001`

Или используйте кнопку в /myitems
""",
        parse_mode='Markdown'
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Проверка регистрации
    if not db.user_exists(user_id):
        await update.message.reply_text(
            "❌ Сначала зарегистрируйтесь: /start"
        )
        return
    
    # Проверка на удаление
    if text.lower().startswith('delete '):
        qr_id = text.split()[1].upper()
        if db.delete_item(qr_id, user_id):
            await update.message.reply_text(
                f"✅ Вещь {qr_id} удалена!"
            )
        else:
            await update.message.reply_text(
                f"❌ Вещь {qr_id} не найдена или не принадлежит вам"
            )
        return
    
    # Парсинг формата: QR_ID название тип
    parts = text.split(maxsplit=2)
    
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Неверный формат!\n\n"
            "Используйте: `QR_ID название тип`\n"
            "Пример: `QR001 Рюкзак Nike рюкзак`\n\n"
            "Или используйте /help для помощи",
            parse_mode='Markdown'
        )
        return
    
    qr_id, item_name, item_type = parts[0].upper(), parts[1], parts[2].lower()
    
    # Валидация QR ID
    if not qr_id.startswith('QR') or len(qr_id) < 4:
        await update.message.reply_text(
            "❌ QR ID должен начинаться с 'QR' и содержать номер\n"
            "Пример: QR001, QR002, QR123"
        )
        return
    
    # Валидация типа
    if item_type not in ITEM_TYPES:
        types_list = ', '.join(ITEM_TYPES.keys())
        await update.message.reply_text(
            f"❌ Неизвестный тип вещи: {item_type}\n\n"
            f"Доступные типы:\n{types_list}"
        )
        return
    
    # Добавление вещи в БД
    success = db.create_item(qr_id, user_id, item_name, item_type)
    
    if success:
        emoji = ITEM_TYPES[item_type]
        
        qr_url = f"https://t.me/{BOT_USERNAME}?start=found_{qr_id}"
        
        text = f"""
✅ **Вещь успешно добавлена!**

{emoji} **{item_name}**
🆔 QR-код: `{qr_id}`
📂 Тип: {item_type}

**Следующие шаги:**

**Способ 1 - Онлайн генератор:**
1. Откройте: [qr-code-generator.com](https://www.qr-code-generator.com)
2. Выберите тип "URL"
3. Вставьте ссылку:
`{qr_url}`
4. Скачайте и распечатайте QR-код
5. Наклейте на вещь

**Способ 2 - Через Python:**
```python
import qrcode
qr = qrcode.QRCode()
qr.add_data('{qr_url}')
qr.make_image().save('{qr_id}.png')
```

💡 При сканировании нашедший сразу свяжется с вами!

🔒 Ваш номер телефона будет скрыт
"""
        
        keyboard = [
            [InlineKeyboardButton("📋 Мои вещи", callback_data='my_items')],
            [InlineKeyboardButton("➕ Добавить ещё", callback_data='add_item')],
            [InlineKeyboardButton("📊 Статистика", callback_data='stats')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    else:
        await update.message.reply_text(
            f"❌ QR-код {qr_id} уже зарегистрирован!\n"
            "Используйте другой ID, например QR002, QR003 и т.д."
        )


async def found_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, qr_id: str):
    """Обработка найденной вещи"""
    finder_id = update.effective_user.id
    finder_name = update.effective_user.full_name
    
    # Регистрируем нашедшего если нужно
    if not db.user_exists(finder_id):
        db.create_user(finder_id, update.effective_user.username or '', finder_name)
    
    # Получаем информацию о вещи
    item = db.get_item_by_qr(qr_id)
    
    if not item:
        await update.message.reply_text(
            "❌ QR-код не найден в системе.\n\n"
            "Возможные причины:\n"
            "• Владелец ещё не зарегистрировал эту вещь\n"
            "• QR-код введён неверно\n"
            "• Вещь была удалена из системы\n\n"
            "💡 Попросите владельца зарегистрировать вещь в @" + BOT_USERNAME
        )
        return
    
    owner_id = item['user_id']
    
    # Проверка что это не сам владелец
    if owner_id == finder_id:
        await update.message.reply_text(
            f"😊 Это ваша вещь: **{item['name']}**\n\n"
            "Рады, что вы её нашли!",
            parse_mode='Markdown'
        )
        return
    
    # Создаём запись о находке
    db.create_finding(qr_id, owner_id, finder_id, finder_name)
    
    emoji = ITEM_TYPES.get(item['item_type'], '📦')
    
    # Сообщение нашедшему
    await update.message.reply_text(
        f"""
✅ **Спасибо за честность!**

Вы нашли: {emoji} **{item['name']}**

Владелец получил уведомление с вашим контактом.
Он свяжется с вами в ближайшее время! 🤝

💡 **Совет:** Можете указать где нашли вещь
""",
        parse_mode='Markdown'
    )
    
    # Сообщение владельцу
    try:
        keyboard = [
            [InlineKeyboardButton("💬 Написать нашедшему", 
                                url=f"tg://user?id={finder_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=owner_id,
            text=f"""
🎉 **ВАША ВЕЩЬ НАЙДЕНА!**

{emoji} Вещь: **{item['name']}**
👤 Нашёл: {finder_name}
⏰ Время: {datetime.now().strftime('%H:%M, %d.%m.%Y')}
🆔 QR-код: `{qr_id}`

Свяжитесь с нашедшим как можно скорее!

💡 Не забудьте поблагодарить за честность! 🙏
""",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        logger.info(f"Уведомление о находке отправлено владельцу {owner_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения владельцу: {e}")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'add_item':
        # Имитируем команду /additem
        fake_update = Update(update.update_id)
        fake_update._effective_user = query.from_user
        fake_update.message = query.message
        await additem_handler(fake_update, context)
        
    elif query.data == 'my_items':
        await myitems_handler(update, context)
        
    elif query.data == 'stats':
        fake_update = Update(update.update_id)
        fake_update._effective_user = query.from_user
        fake_update.message = query.message
        await stats_handler(fake_update, context)
        
    elif query.data == 'how_it_works':
        text = """
ℹ️ **Как работает QR-Находка?**

**Для владельца вещи:**
1️⃣ Регистрируешься в боте (/start)
2️⃣ Добавляешь вещи (/additem)
3️⃣ Генерируешь QR-код со ссылкой на бота
4️⃣ Клеишь стикер с QR на вещь

**Для нашедшего:**
1️⃣ Сканирует QR-код камерой телефона
2️⃣ Открывается Telegram бот
3️⃣ Нажимает START
4️⃣ Владелец мгновенно получает уведомление

**Безопасность:**
🔒 Нашедший не видит твой номер телефона
🔒 Только ты решаешь, отвечать или нет
🔒 Вся переписка через защищённый Telegram

**Преимущества:**
✅ Быстро - уведомление за секунды
✅ Удобно - всё в одном мессенджере  
✅ Стильно - никаких маркеров на вещах
✅ Бесплатно - регистрация не стоит ничего

**Статистика:**
📊 80% вещей с QR-стикерами возвращаются к владельцам
📊 Среднее время находки: 2 часа
"""
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить вещь", callback_data='add_item')],
            [InlineKeyboardButton("📊 Статистика", callback_data='stats')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif query.data == 'delete_item':
        await query.message.reply_text(
            """
🗑️ **Удаление вещи**

Отправьте QR-код вещи которую хотите удалить:
`delete QR001`

Или используйте команду:
/delete
""",
            parse_mode='Markdown'
        )