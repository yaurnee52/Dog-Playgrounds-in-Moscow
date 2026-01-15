from datetime import date, datetime, timedelta

import mysql.connector
from flask import Flask, jsonify, render_template, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)


DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "",
    "database": "dog_walking_areas",
    "port": 3306,
    "use_pure": True,
}

SLOT_HOURS = list(range(0, 24))
CATEGORY_LABELS = {
    "SMALL": "Декоративные",
    "STANDARD": "Стандартные",
    "ACTIVE": "Активные",
    "HIGH_RISK": "Служебные / Бойцовские",
}


def get_db():
    return mysql.connector.connect(**DB_CONFIG)



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
        # Assumption: allow a second HIGH_RISK only if slot already has exactly one HIGH_RISK.
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/map")
def map_view():
    return render_template("map.html")


@app.route("/api/playgrounds")
def get_playgrounds():
    district = request.args.get("district")
    if district:
        district = district.strip()
    try:
        with get_db() as conn:
            with conn.cursor(dictionary=True) as cur:
                if district:
                    cur.execute(
                        """
                        SELECT id,
                               CAST(lat AS DOUBLE) AS lat,
                               CAST(lon AS DOUBLE) AS lon
                        FROM playgrounds
                        WHERE lat IS NOT NULL AND lon IS NOT NULL
                          AND TRIM(district) = %s
                        """,
                        (district,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id,
                               CAST(lat AS DOUBLE) AS lat,
                               CAST(lon AS DOUBLE) AS lon
                        FROM playgrounds
                        WHERE lat IS NOT NULL AND lon IS NOT NULL
                        """
                    )
                rows = cur.fetchall()
        return jsonify(rows)
    except mysql.connector.Error as exc:
        return jsonify({"error": "Database error", "details": str(exc)}), 500


@app.route("/api/playgrounds/search")
def search_playgrounds():
    district = request.args.get("district")
    if not district:
        return jsonify({"error": "District is required"}), 400
    district = district.strip()
    try:
        with get_db() as conn:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(
                    """
                    SELECT id, park_name, address, district,
                           CAST(lat AS DOUBLE) AS lat,
                           CAST(lon AS DOUBLE) AS lon
                    FROM playgrounds
                    WHERE TRIM(district) = %s
                    ORDER BY id
                    """,
                    (district,),
                )
                rows = cur.fetchall()
        return jsonify(rows)
    except mysql.connector.Error as exc:
        return jsonify({"error": "Database error", "details": str(exc)}), 500


@app.route("/api/districts")
def get_districts():
    try:
        with get_db() as conn:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(
                    """
                    SELECT DISTINCT TRIM(district) AS district
                    FROM playgrounds
                    WHERE district IS NOT NULL AND TRIM(district) <> ''
                    ORDER BY district
                    """
                )
                rows = cur.fetchall()
        return jsonify([row["district"] for row in rows])
    except mysql.connector.Error as exc:
        return jsonify({"error": "Database error", "details": str(exc)}), 500


@app.route("/api/diagnostics")
def diagnostics():
    try:
        with get_db() as conn:
            with conn.cursor(dictionary=True) as cur:
                cur.execute("SELECT DATABASE() AS db")
                db_row = cur.fetchone()
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    """,
                    (DB_CONFIG["database"],),
                )
                tables = [row["table_name"] for row in cur.fetchall()]
                cur.execute("SELECT COUNT(*) AS total FROM playgrounds")
                total_playgrounds = cur.fetchone()["total"]
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT TRIM(district)) AS total
                    FROM playgrounds
                    WHERE district IS NOT NULL AND TRIM(district) <> ''
                    """
                )
                total_districts = cur.fetchone()["total"]
                cur.execute(
                    """
                    SELECT TRIM(district) AS district
                    FROM playgrounds
                    WHERE district IS NOT NULL AND TRIM(district) <> ''
                    LIMIT 5
                    """
                )
                sample_districts = [row["district"] for row in cur.fetchall()]
        return jsonify(
            {
                "db": db_row["db"],
                "tables": tables,
                "playgrounds_total": total_playgrounds,
                "districts_total": total_districts,
                "sample_districts": sample_districts,
            }
        )
    except mysql.connector.Error as exc:
        return jsonify({"error": "Database error", "details": str(exc)}), 500


@app.route("/api/playgrounds/<int:playground_id>/details")
def get_playground_details(playground_id):
    requested_category = request.args.get("category", "STANDARD").upper()
    dog_id = request.args.get("dog_id")
    if dog_id:
        try:
            dog_id = int(dog_id)
        except ValueError:
            dog_id = None
    if dog_id:
        with get_db() as conn:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(
                    """
                    SELECT bc.code AS category_code
                    FROM dogs d
                    JOIN breed_categories bc ON d.category_id = bc.id
                    WHERE d.id = %s
                    """,
                    (dog_id,),
                )
                dog_row = cur.fetchone()
        if dog_row and dog_row.get("category_code"):
            requested_category = dog_row["category_code"]
    if requested_category not in CATEGORY_LABELS:
        requested_category = "STANDARD"

    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT id, adm_area, district, address, park_name, area, elements,
                       lighting, fencing, working_hours, photo_id, lat, lon
                FROM playgrounds
                WHERE id = %s
                """,
                (playground_id,),
            )
            row = cur.fetchone()

    if not row:
        return jsonify({"error": "Playground not found"}), 404

    today = date.today()
    slots = build_slot_statuses(playground_id, today, requested_category)
    row["photo_url"] = parse_photo_url(row.get("photo_id"))
    row["requested_category"] = requested_category
    row["slots"] = slots
    return jsonify(row)


@app.route("/api/book", methods=["POST"])
def book_slot():
    payload = request.get_json(silent=True) or {}
    playground_id = payload.get("playground_id")
    slot_hour = payload.get("slot_hour")
    dog_id = payload.get("dog_id")
    slot_date = payload.get("slot_date") or str(date.today())

    try:
        playground_id = int(playground_id)
        slot_hour = int(slot_hour)
        dog_id = int(dog_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid playground, hour, or dog"}), 400
    if slot_hour not in SLOT_HOURS:
        return jsonify({"error": "Invalid slot hour"}), 400

    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT bc.code AS category_code
                FROM dogs d
                JOIN breed_categories bc ON d.category_id = bc.id
                WHERE d.id = %s
                """,
                (dog_id,),
            )
            dog_row = cur.fetchone()
    if not dog_row:
        return jsonify({"error": "Dog not found"}), 404
    category_code = dog_row["category_code"]

    try:
        start_time = datetime.fromisoformat(slot_date).replace(
            hour=slot_hour, minute=0, second=0, microsecond=0
        )
    except ValueError:
        return jsonify({"error": "Invalid slot date"}), 400
    end_time = start_time + timedelta(hours=1)

    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT bc.code AS category_code
                FROM bookings b
                JOIN dogs d ON b.dog_id = d.id
                JOIN breed_categories bc ON d.category_id = bc.id
                WHERE b.playground_id = %s
                  AND DATE(b.start_time) = %s
                  AND HOUR(b.start_time) = %s
                  AND b.status = 'confirmed'
                """,
                (playground_id, slot_date, slot_hour),
            )
            existing = [row["category_code"] for row in cur.fetchall()]

            allowed, limit = evaluate_slot(existing, category_code)
            if not allowed or len(existing) >= limit:
                return (
                    jsonify({"error": "Slot is not available for this category"}),
                    409,
                )

            cur.execute(
                """
                INSERT INTO bookings (playground_id, dog_id, start_time, end_time, status)
                VALUES (%s, %s, %s, %s, 'confirmed')
                """,
                (playground_id, dog_id, start_time, end_time),
            )
        conn.commit()

    return jsonify({"success": True})


@app.route("/api/dogs")
def get_dogs():
    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT d.id, d.name, bc.code AS category_code
                FROM dogs d
                JOIN breed_categories bc ON d.category_id = bc.id
                ORDER BY d.name
                """
            )
            rows = cur.fetchall()
    return jsonify(rows)


@app.route("/api/register", methods=["POST"])
def register_user():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    dog_name = (payload.get("dog_name") or "").strip()
    dog_breed = (payload.get("dog_breed") or "").strip() or None
    dog_category = (payload.get("dog_category") or "").strip().upper()

    if not all([username, email, password, dog_name, dog_category]):
        return jsonify({"error": "Missing required fields"}), 400
    if dog_category not in CATEGORY_LABELS:
        return jsonify({"error": "Invalid dog category"}), 400

    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT id FROM users WHERE email = %s LIMIT 1",
                (email,),
            )
            if cur.fetchone():
                return jsonify({"error": "Email already exists"}), 409

            cur.execute(
                "SELECT id FROM breed_categories WHERE code = %s",
                (dog_category,),
            )
            category_row = cur.fetchone()
            if not category_row:
                return jsonify({"error": "Dog category not found"}), 400

            password_hash = generate_password_hash(password)
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                """,
                (username, email, password_hash),
            )
            user_id = cur.lastrowid
            cur.execute(
                """
                INSERT INTO dogs (user_id, category_id, name, breed)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, category_row["id"], dog_name, dog_breed),
            )
        conn.commit()

    return jsonify({"success": True})


@app.route("/api/login", methods=["POST"])
def login_user():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Missing credentials"}), 400

    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT id, username, password_hash
                FROM users
                WHERE email = %s
                """,
                (email,),
            )
            user_row = cur.fetchone()

    if not user_row or not check_password_hash(
        user_row["password_hash"], password
    ):
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({"success": True, "user_id": user_row["id"], "username": user_row["username"]})


if __name__ == "__main__":
    app.run(debug=True)
