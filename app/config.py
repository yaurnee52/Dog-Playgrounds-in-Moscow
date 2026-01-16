import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": int(os.getenv("DB_PORT")),
    "use_pure": os.getenv("DB_USE_PURE", "True").lower() == "true",
}

SLOT_HOURS = list(range(0, 24))

CATEGORY_LABELS = {
    "SMALL": "Декоративные",
    "STANDARD": "Стандартные",
    "ACTIVE": "Активные",
    "HIGH_RISK": "Служебные / Бойцовские",
}
