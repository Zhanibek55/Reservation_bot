from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import io
from typing import List, Tuple
from functools import lru_cache
from config import get_table_layout

# Удаляем декоратор lru_cache, так как он не работает с нехешируемыми типами (списками)
# @lru_cache(maxsize=16)
def create_table_layout_image(tables, width: int = 800, height: int = 600) -> bytes:
    """
    Создает изображение с расположением столов
    
    Args:
        tables: Список или кортеж с данными о столах
        width: Ширина изображения
        height: Высота изображения
        
    Returns:
        bytes: Изображение в формате PNG
    """
    # Преобразуем в кортеж для кэширования, если передан список
    if isinstance(tables, list):
        tables_tuple = tuple(tuple(sorted(t.items())) for t in tables)
        # Создаем словарь для быстрого доступа к данным
        tables_dict = {t['number']: t for t in tables}
    else:
        tables_tuple = tables
        # Если уже кортеж, создаем словарь из него
        tables_dict = {}
        for t in tables:
            # Преобразуем кортеж пар ключ-значение в словарь
            t_dict = dict(t)
            if 'number' in t_dict:
                tables_dict[t_dict['number']] = t_dict
    
    layout = get_table_layout()
    image = Image.new('RGB', (width, height), '#f0f0f0')
    draw = ImageDraw.Draw(image)
    draw.line([(200, 0), (200, 600)], fill='black', width=4)
    draw.line([(0, 300), (200, 300)], fill='black', width=4)
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
        except:
            font = ImageFont.load_default()
    
    for table_layout in layout:
        table_number = table_layout['number']
        if table_number in tables_dict:
            table_data = tables_dict[table_number]
            color = 'green' if table_data['is_available'] else 'red'
            draw.rectangle([
                table_layout['x'],
                table_layout['y'],
                table_layout['x'] + table_layout['width'],
                table_layout['y'] + table_layout['height']
            ], fill=color, outline='black', width=3)
            text = str(table_layout['number'])
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = table_layout['x'] + (table_layout['width'] - text_width) // 2
            text_y = table_layout['y'] + (table_layout['height'] - text_height) // 2
            draw.text((text_x, text_y), text, fill='white', font=font)
    
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()

def get_time_slots(opening_time: str, closing_time: str, slot_duration: int) -> List[Tuple[datetime, datetime]]:
    today = datetime.now().date()
    opening = datetime.strptime(opening_time, "%H:%M").time()
    closing = datetime.strptime(closing_time, "%H:%M").time()
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
    return f"{slot[0].strftime('%H:%M')} - {slot[1].strftime('%H:%M')}"

def is_slot_available(table_id: int, start_time: datetime, end_time: datetime, reservations: List[dict]) -> bool:
    for r in reservations:
        if r['table_id'] == table_id and r['status'] == 'confirmed':
            if not (end_time <= r['start_time'] or start_time >= r['end_time']):
                return False
    return True
