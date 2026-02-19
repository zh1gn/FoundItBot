"""
Веб-сервер для QR-Находка
Показывает страницу при сканировании QR-кода
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS
import logging

from config.config import WEB_HOST, WEB_PORT, DATABASE_PATH, BOT_USERNAME, ITEM_TYPES
from database.models import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создание Flask приложения
app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')
CORS(app)

# База данных
db = Database(DATABASE_PATH)


@app.route('/')
def index():
    """Главная страница"""
    stats = db.get_statistics()
    return render_template('index.html', stats=stats, bot_username=BOT_USERNAME)


@app.route('/found/<qr_id>')
def found_item(qr_id):
    """Страница найденной вещи"""
    qr_id = qr_id.upper()
    
    # Получаем информацию о вещи
    item = db.get_item_by_qr(qr_id)
    
    if not item:
        return render_template('not_found.html', qr_id=qr_id, bot_username=BOT_USERNAME)
    
    # Получаем эмодзи для типа вещи
    emoji = ITEM_TYPES.get(item['item_type'], '📦')
    
    # Формируем ссылку на бота
    bot_link = f"https://t.me/{BOT_USERNAME}?start=found_{qr_id}"
    
    return render_template('found.html', 
                         item=item, 
                         emoji=emoji,
                         bot_link=bot_link,
                         qr_id=qr_id)


@app.route('/api/item/<qr_id>')
def get_item(qr_id):
    """API для получения информации о вещи"""
    qr_id = qr_id.upper()
    item = db.get_item_by_qr(qr_id)
    
    if not item:
        return jsonify({'error': 'Item not found'}), 404
    
    return jsonify({
        'qr_id': item['qr_id'],
        'name': item['name'],
        'type': item['item_type'],
        'emoji': ITEM_TYPES.get(item['item_type'], '📦'),
        'bot_username': BOT_USERNAME
    })


@app.route('/api/stats')
def get_stats():
    """API для получения статистики"""
    stats = db.get_statistics()
    return jsonify(stats)


@app.route('/qr/<qr_id>')
def qr_redirect(qr_id):
    """Редирект для коротких ссылок"""
    return redirect(url_for('found_item', qr_id=qr_id))


@app.errorhandler(404)
def not_found(error):
    """Обработка 404 ошибки"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Обработка 500 ошибки"""
    logger.error(f"Internal error: {error}")
    return render_template('500.html'), 500


def run_web_server():
    """Запуск веб-сервера"""
    logger.info(f"🌐 Веб-сервер запущен на http://{WEB_HOST}:{WEB_PORT}")
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False)


if __name__ == '__main__':
    run_web_server()