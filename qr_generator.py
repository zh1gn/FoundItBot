"""
Утилиты для генерации QR-кодов
"""
import qrcode
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import logging

from config.config import QR_CODE_SIZE, QR_CODE_BORDER, BOT_USERNAME, ITEM_TYPES

logger = logging.getLogger(__name__)


class QRGenerator:
    """Генератор QR-кодов для стикеров"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path(__file__).parent.parent / 'qr_codes'
        self.output_dir.mkdir(exist_ok=True, parents=True)
    
    def generate_simple_qr(self, qr_id: str, save_path: str = None) -> str:
        """
        Генерация простого QR-кода
        
        Args:
            qr_id: ID QR-кода (например, QR001)
            save_path: Путь для сохранения (опционально)
        
        Returns:
            Путь к созданному файлу
        """
        # Формируем URL для бота
        url = f"https://t.me/{BOT_USERNAME}?start=found_{qr_id}"
        
        # Создаём QR-код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=QR_CODE_SIZE,
            border=QR_CODE_BORDER,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        # Генерируем изображение
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Сохраняем
        if not save_path:
            save_path = self.output_dir / f"{qr_id}.png"
        
        img.save(save_path)
        logger.info(f"QR-код создан: {save_path}")
        
        return str(save_path)
    
    def generate_styled_qr(self, qr_id: str, item_name: str, item_type: str, 
                          size: tuple = (300, 350), save_path: str = None) -> str:
        """
        Генерация стилизованного QR-кода со стикером
        
        Args:
            qr_id: ID QR-кода
            item_name: Название вещи
            item_type: Тип вещи
            size: Размер итогового изображения (ширина, высота)
            save_path: Путь для сохранения
        
        Returns:
            Путь к созданному файлу
        """
        # Генерируем базовый QR-код
        temp_path = self.output_dir / f"temp_{qr_id}.png"
        self.generate_simple_qr(qr_id, str(temp_path))
        
        # Открываем QR-код
        qr_img = Image.open(temp_path)
        
        # Создаём новое изображение с местом для текста
        new_img = Image.new('RGB', size, 'white')
        draw = ImageDraw.Draw(new_img)
        
        # Размещаем QR-код по центру
        qr_size = min(size[0] - 40, size[1] - 100)  # Оставляем место для текста
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        qr_position = ((size[0] - qr_size) // 2, 20)
        new_img.paste(qr_img, qr_position)
        
        # Добавляем эмодзи типа вещи (если возможно)
        emoji = ITEM_TYPES.get(item_type, '📦')
        
        # Добавляем текст
        try:
            # Пытаемся использовать системный шрифт
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            # Fallback на дефолтный шрифт
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
        
        # Заголовок
        title = "QR-Находка"
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((size[0] - title_width) // 2, qr_size + 30), 
                 title, fill='#667eea', font=title_font)
        
        # ID
        id_text = f"{emoji} {qr_id}"
        id_bbox = draw.textbbox((0, 0), id_text, font=text_font)
        id_width = id_bbox[2] - id_bbox[0]
        draw.text(((size[0] - id_width) // 2, qr_size + 60), 
                 id_text, fill='#1e293b', font=text_font)
        
        # Сохраняем
        if not save_path:
            save_path = self.output_dir / f"{qr_id}_styled.png"
        
        new_img.save(save_path)
        
        # Удаляем временный файл
        temp_path.unlink()
        
        logger.info(f"Стилизованный QR-код создан: {save_path}")
        return str(save_path)
    
    def generate_batch(self, items: list, styled: bool = False) -> list:
        """
        Массовая генерация QR-кодов
        
        Args:
            items: Список словарей с ключами: qr_id, item_name, item_type
            styled: Использовать стилизацию
        
        Returns:
            Список путей к созданным файлам
        """
        paths = []
        
        for item in items:
            try:
                if styled:
                    path = self.generate_styled_qr(
                        item['qr_id'],
                        item['item_name'],
                        item['item_type']
                    )
                else:
                    path = self.generate_simple_qr(item['qr_id'])
                
                paths.append(path)
            except Exception as e:
                logger.error(f"Ошибка генерации QR для {item['qr_id']}: {e}")
        
        logger.info(f"Сгенерировано {len(paths)} QR-кодов")
        return paths


def generate_printable_sheet(qr_paths: list, output_path: str = None, 
                            stickers_per_row: int = 3) -> str:
    """
    Создать лист для печати с несколькими QR-кодами
    
    Args:
        qr_paths: Список путей к QR-кодам
        output_path: Путь для сохранения листа
        stickers_per_row: Количество стикеров в ряду
    
    Returns:
        Путь к созданному файлу
    """
    # Размеры листа A4 в пикселях (300 DPI)
    a4_width, a4_height = 2480, 3508
    margin = 100
    spacing = 50
    
    # Открываем первое изображение чтобы узнать размер
    first_img = Image.open(qr_paths[0])
    sticker_width, sticker_height = first_img.size
    
    # Вычисляем количество рядов
    rows = (len(qr_paths) + stickers_per_row - 1) // stickers_per_row
    
    # Создаём лист
    sheet = Image.new('RGB', (a4_width, a4_height), 'white')
    
    # Размещаем QR-коды
    for idx, qr_path in enumerate(qr_paths):
        row = idx // stickers_per_row
        col = idx % stickers_per_row
        
        x = margin + col * (sticker_width + spacing)
        y = margin + row * (sticker_height + spacing)
        
        # Проверяем что не выходим за границы
        if y + sticker_height > a4_height - margin:
            break
        
        qr_img = Image.open(qr_path)
        sheet.paste(qr_img, (x, y))
    
    # Сохраняем
    if not output_path:
        output_path = Path(__file__).parent.parent / 'qr_codes' / 'print_sheet.png'
    
    sheet.save(output_path, dpi=(300, 300))
    logger.info(f"Лист для печати создан: {output_path}")
    
    return str(output_path)


# Пример использования
if __name__ == '__main__':
    # Создаём генератор
    generator = QRGenerator()
    
    # Генерируем простой QR
    generator.generate_simple_qr('QR001')
    
    # Генерируем стилизованный QR
    generator.generate_styled_qr('QR002', 'Рюкзак Nike', 'рюкзак')
    
    # Массовая генерация
    items = [
        {'qr_id': 'QR003', 'item_name': 'Ключи', 'item_type': 'ключи'},
        {'qr_id': 'QR004', 'item_name': 'Сменка', 'item_type': 'обувь'},
        {'qr_id': 'QR005', 'item_name': 'Куртка', 'item_type': 'куртка'},
    ]
    paths = generator.generate_batch(items, styled=True)
    
    # Создаём лист для печати
    generate_printable_sheet(paths)
    
    print("✅ QR-коды успешно сгенерированы!")
    print(f"📁 Файлы находятся в: {generator.output_dir}")