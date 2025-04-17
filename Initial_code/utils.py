from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import io
from typing import List, Tuple
from config import TABLE_LAYOUT

def create_table_layout(tables: List[dict], width: int = 800, height: int = 600) -> bytes:
    """Создает изображение с расположением столов согласно SVG макету"""
    image = Image.new('RGB', (width, height), '#f0f0f0')  # Используем тот же фоновый цвет, что и в SVG
    draw = ImageDraw.Draw(image)
    
    # Рисуем стены
    draw.line([(200, 0), (200, 600)], fill='black', width=4)
    draw.line([(0, 300), (200, 300)], fill='black', width=4)
    
    # Загружаем шрифт
    try:
        font = ImageFont.truetype("arial.ttf", 32)  # Увеличили размер шрифта до 128
    except:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)  # Пробуем использовать DejaVu Sans Bold
        except:
            font = ImageFont.load_default()
            # Увеличиваем размер текста для стандартного шрифта
            font_size = 128
    
    # Рисуем столы согласно макету
    for table_layout in TABLE_LAYOUT:
        table_data = next((t for t in tables if t['number'] == table_layout['number']), None)
        if table_data:
            # Определяем цвет стола
            color = 'green' if table_data['is_available'] else 'red'
            
            # Рисуем стол
            draw.rectangle(
                [
                    table_layout['x'],
                    table_layout['y'],
                    table_layout['x'] + table_layout['width'],
                    table_layout['y'] + table_layout['height']
                ],
                fill=color,
                outline='black',
                width=3
            )
            
            # Добавляем номер стола
            text = str(table_layout['number'])
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            text_x = table_layout['x'] + (table_layout['width'] - text_width) // 2
            text_y = table_layout['y'] + (table_layout['height'] - text_height) // 2
            draw.text((text_x, text_y), text, fill='white', font=font)  # Изменили цвет текста на белый
    
    # Конвертируем изображение в bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr.getvalue()

def get_time_slots(opening_time: str, closing_time: str, slot_duration: int) -> List[Tuple[datetime, datetime]]:
    """Генерирует временные слоты для бронирования"""
    today = datetime.now().date()
    
    # Парсим время открытия и закрытия
    opening = datetime.strptime(opening_time, "%H:%M").time()
    closing = datetime.strptime(closing_time, "%H:%M").time()
    
    # Создаем datetime объекты
    start = datetime.combine(today, opening)
    end = datetime.combine(today, closing)
    
    slots = []
    current = start
    
    while current + timedelta(minutes=slot_duration) <= end:
        slot_end = current + timedelta(minutes=slot_duration)
        slots.append((current, slot_end))
        current = slot_end
    
    return slots

def format_time_slot(slot: Tuple[datetime, datetime]) -> str:
    """Форматирует временной слот для отображения"""
    return f"{slot[0].strftime('%H:%M')} - {slot[1].strftime('%H:%M')}"

def is_slot_available(table_id: int, start_time: datetime, end_time: datetime, reservations: List[dict]) -> bool:
    """Проверяет, доступен ли временной слот для бронирования"""
    for reservation in reservations:
        if reservation['table_id'] == table_id:
            res_start = reservation['start_time']
            res_end = reservation['end_time']
            
            # Проверяем пересечение временных интервалов
            if not (end_time <= res_start or start_time >= res_end):
                return False
    
    return True 