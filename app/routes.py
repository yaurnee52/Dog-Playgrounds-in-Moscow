from datetime import date, datetime, timedelta

import mysql.connector
from flask import Blueprint, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .config import CATEGORY_LABELS, DB_CONFIG, SLOT_HOURS
from .db import get_db
from .services import build_slot_statuses, parse_photo_url, evaluate_slot, clean_park_name

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/map")
def map_view():
    return render_template("map.html")


@bp.route("/profile")
def profile_view():
    return render_template("profile.html")

@bp.route("/api/playgrounds")
def get_playgrounds():
    district = request.args.get("district")
    if district:
        district = district.strip()
    
    # Получаем фильтры
    lighting = request.args.get("lighting")
    fencing = request.args.get("fencing")
    elements = request.args.get("elements")
    
    try:
        with get_db() as conn:
            with conn.cursor(dictionary=True) as cur:
                if district:
                    query = """
                        SELECT id,
                               CAST(lat AS DOUBLE) AS lat,
                               CAST(lon AS DOUBLE) AS lon
                        FROM playgrounds
                        WHERE lat IS NOT NULL AND lon IS NOT NULL
                          AND TRIM(district) = %s
                    """
                    params = [district]
                    
                    # Добавляем фильтры
                    if lighting:
                        query += " AND lighting = 'да'"
                    if fencing:
                        query += " AND fencing = 'да'"
                    if elements:
                        query += " AND elements IS NOT NULL AND elements <> '' AND elements <> '[]'"
                    
                    cur.execute(query, params)
                else:
                    query = """
                        SELECT id,
                               CAST(lat AS DOUBLE) AS lat,
                               CAST(lon AS DOUBLE) AS lon
                        FROM playgrounds
                        WHERE lat IS NOT NULL AND lon IS NOT NULL
                    """
                    params = []
                    
                    # Добавляем фильтры
                    if lighting:
                        query += " AND lighting = 'да'"
                    if fencing:
                        query += " AND fencing = 'да'"
                    if elements:
                        query += " AND elements IS NOT NULL AND elements <> '' AND elements <> '[]'"
                    
                    cur.execute(query, params)
                rows = cur.fetchall()
        return jsonify(rows)
    except mysql.connector.Error as exc:
        return jsonify({"error": "Database error", "details": str(exc)}), 500


@bp.route("/api/playgrounds/search")
def search_playgrounds():
    district = request.args.get("district")
    if not district:
        return jsonify({"error": "District is required"}), 400
    district = district.strip()
    
    # Получаем фильтры
    lighting = request.args.get("lighting")
    fencing = request.args.get("fencing")
    elements = request.args.get("elements")
    
    try:
        with get_db() as conn:
            with conn.cursor(dictionary=True) as cur:
                query = """
                    SELECT id, park_name, address, district, lighting, fencing, elements,
                           CAST(lat AS DOUBLE) AS lat,
                           CAST(lon AS DOUBLE) AS lon
                    FROM playgrounds
                    WHERE TRIM(district) = %s
                """
                params = [district]
                
                # Добавляем фильтры
                if lighting:
                    query += " AND lighting = 'да'"
                if fencing:
                    query += " AND fencing = 'да'"
                if elements:
                    query += " AND elements IS NOT NULL AND elements <> '' AND elements <> '[]'"
                
                query += " ORDER BY id"
                
                cur.execute(query, params)
                rows = cur.fetchall()
        
        for row in rows:
            row["park_name"] = clean_park_name(row["park_name"])

        return jsonify(rows)
    except mysql.connector.Error as exc:
        return jsonify({"error": "Database error", "details": str(exc)}), 500


@bp.route("/api/districts")
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


@bp.route("/api/playgrounds/<int:playground_id>/details")
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
    row["park_name"] = clean_park_name(row.get("park_name"))
    row["requested_category"] = requested_category
    row["slots"] = slots
    return jsonify(row)


@bp.route("/api/book", methods=["POST"])
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
                SELECT id FROM bookings
                WHERE dog_id = %s
                  AND DATE(start_time) = %s
                  AND HOUR(start_time) = %s
                  AND status = 'confirmed'
                LIMIT 1
                """,
                (dog_id, slot_date, slot_hour),
            )
            if cur.fetchone():
                return jsonify({"error": "Собака уже записана на это время."}), 409

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


@bp.route("/api/dogs")
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


@bp.route("/api/me")
def get_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authorized"}), 401
    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT id, username, email, created_at
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            user_row = cur.fetchone()
    if not user_row:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user_row)


@bp.route("/api/my-dogs")
def get_my_dogs():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authorized"}), 401
    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT d.id, d.name, d.breed, bc.code AS category_code
                FROM dogs d
                JOIN breed_categories bc ON d.category_id = bc.id
                WHERE d.user_id = %s
                ORDER BY d.name
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    return jsonify(rows)


@bp.route("/api/my-bookings")
def get_my_bookings():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authorized"}), 401
    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT b.id, b.start_time, b.end_time, b.status,
                       d.name AS dog_name,
                       p.id AS playground_id,
                       p.park_name, p.address
                FROM bookings b
                JOIN dogs d ON b.dog_id = d.id
                JOIN playgrounds p ON b.playground_id = p.id
                WHERE d.user_id = %s
                ORDER BY b.start_time DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()

    for row in rows:
        row["park_name"] = clean_park_name(row["park_name"])

    return jsonify(rows)


@bp.route("/api/dogs/add", methods=["POST"])
def add_dog():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authorized"}), 401
    payload = request.get_json(silent=True) or {}
    dog_name = (payload.get("dog_name") or "").strip()
    dog_breed = (payload.get("dog_breed") or "").strip() or None
    dog_category = (payload.get("dog_category") or "").strip().upper()

    if not dog_name or not dog_category:
        return jsonify({"error": "Missing required fields"}), 400
    if dog_category not in CATEGORY_LABELS:
        return jsonify({"error": "Invalid dog category"}), 400

    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT id FROM breed_categories WHERE code = %s",
                (dog_category,),
            )
            category_row = cur.fetchone()
            if not category_row:
                return jsonify({"error": "Dog category not found"}), 400

            cur.execute(
                """
                INSERT INTO dogs (user_id, category_id, name, breed)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, category_row["id"], dog_name, dog_breed),
            )
        conn.commit()

    return jsonify({"success": True})


@bp.route("/api/register", methods=["POST"])
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
                "SELECT id FROM users WHERE username = %s LIMIT 1",
                (username,),
            )
            if cur.fetchone():
                return jsonify({"error": "Username already exists"}), 409

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


@bp.route("/api/logout", methods=["POST"])
def logout_user():
    session.pop("user_id", None)
    return jsonify({"success": True})


@bp.route("/api/login", methods=["POST"])
def login_user():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400

    with get_db() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT id, username, password_hash
                FROM users
                WHERE username = %s
                """,
                (username,),
            )
            user_row = cur.fetchone()

    if not user_row or not check_password_hash(
        user_row["password_hash"], password
    ):
        return jsonify({"error": "Invalid username or password"}), 401

    session["user_id"] = user_row["id"]
    return jsonify({"success": True, "user_id": user_row["id"], "username": user_row["username"]})


@bp.route("/api/diagnostics")
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
