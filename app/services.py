import re
from .config import SLOT_HOURS
from .db import get_db


def clean_park_name(raw_name):
    """
    Extracts 'value' from strings like: {global_id=4331863, value=Парк «50-летия Октября»}
    Or returns the raw name if it doesn't match the pattern.
    """
    if not raw_name or raw_name == "[]":
        return None
    
    # Try to find value=... pattern
    match = re.search(r"value=([^}]+)", raw_name)
    if match:
        return match.group(1).strip()
    
    return raw_name.strip()


def parse_photo_url(photo_id_text):
    if not photo_id_text:
        return None
    for line in photo_id_text.splitlines():
        line = line.strip()
        if line.lower().startswith("photo:"):
            photo_id = line.split(":", 1)[1].strip()
            if photo_id:
                return f"https://op.mos.ru/MEDIA/showFile?id={photo_id}"
    return None


def get_slot_bookings(playground_id, slot_date):
    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT HOUR(b.start_time) AS slot_hour, bc.code AS category_code
                FROM bookings b
                JOIN dogs d ON b.dog_id = d.id
                JOIN breed_categories bc ON d.category_id = bc.id
                WHERE b.playground_id = %s
                  AND DATE(b.start_time) = %s
                  AND b.status = 'confirmed'
                """,
                (playground_id, slot_date),
            )
            rows = cur.fetchall()
    bookings_by_hour = {hour: [] for hour in SLOT_HOURS}
    for row in rows:
        hour = int(row["slot_hour"])
        if hour in bookings_by_hour:
            bookings_by_hour[hour].append(row["category_code"])
    return bookings_by_hour


def evaluate_slot(existing_categories, requested_category):
    count = len(existing_categories)
    has_high = "HIGH_RISK" in existing_categories
    has_small = "SMALL" in existing_categories
    has_standard = "STANDARD" in existing_categories
    has_active = "ACTIVE" in existing_categories

    if requested_category == "HIGH_RISK":
        if count == 0:
            return True, 2
        if has_high and count == 1:
            return True, 2
        return False, 2

    if has_high:
        return False, 2

    if requested_category == "SMALL":
        if count == 0:
            return True, 8
        if has_small and count < 8:
            return True, 8
        return False, 8

    if has_small:
        return False, 8

    if requested_category in {"STANDARD", "ACTIVE"}:
        if has_standard or has_active or count == 0:
            return count < 8, 8

    return False, 8


def build_slot_statuses(playground_id, slot_date, requested_category):
    bookings_by_hour = get_slot_bookings(playground_id, slot_date)
    slots = []
    for hour in SLOT_HOURS:
        existing = bookings_by_hour.get(hour, [])
        allowed, limit = evaluate_slot(existing, requested_category)
        count = len(existing)
        if count == 0:
            status = "free"
        elif allowed and count < limit:
            status = "joinable"
        else:
            status = "full"
        slots.append(
            {
                "hour": hour,
                "label": f"{hour:02d}:00",
                "status": status,
                "count": count,
                "limit": limit,
                "categories": existing,
            }
        )
    return slots
