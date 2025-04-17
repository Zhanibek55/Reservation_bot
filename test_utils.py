import pytest
from utils import get_time_slots, is_slot_available, format_time_slot
from datetime import datetime, timedelta

def test_get_time_slots():
    slots = get_time_slots("10:00", "12:00", 30)
    today = datetime.now().date()
    expected = [
        (datetime.combine(today, datetime.strptime("10:00", "%H:%M").time()),
         datetime.combine(today, datetime.strptime("10:30", "%H:%M").time())),
        (datetime.combine(today, datetime.strptime("10:30", "%H:%M").time()),
         datetime.combine(today, datetime.strptime("11:00", "%H:%M").time())),
        (datetime.combine(today, datetime.strptime("11:00", "%H:%M").time()),
         datetime.combine(today, datetime.strptime("11:30", "%H:%M").time())),
        (datetime.combine(today, datetime.strptime("11:30", "%H:%M").time()),
         datetime.combine(today, datetime.strptime("12:00", "%H:%M").time())),
    ]
    assert slots == expected

def test_is_slot_available():
    table_id = 1
    slot_start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    slot_end = slot_start.replace(minute=30)
    reservations = [
        {'table_id': 1, 'start_time': slot_start, 'end_time': slot_end, 'status': 'confirmed'},
        {'table_id': 1, 'start_time': slot_start.replace(hour=11), 'end_time': slot_start.replace(hour=11, minute=30), 'status': 'confirmed'},
    ]
    assert not is_slot_available(table_id, slot_start, slot_end, reservations)
    slot2_start = slot_start.replace(hour=10, minute=30)
    slot2_end = slot_start.replace(hour=11, minute=0)
    assert is_slot_available(table_id, slot2_start, slot2_end, reservations)

def test_format_time_slot():
    slot = (datetime(2025, 4, 17, 10, 0), datetime(2025, 4, 17, 10, 30))
    assert format_time_slot(slot) == "10:00 - 10:30"
