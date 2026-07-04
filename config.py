import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


class Config:
    DATABASE_URL = os.getenv('DATABASE_URL')

    if DATABASE_URL:
        _parsed = urlparse(DATABASE_URL)
        DB_NAME = (_parsed.path or '').lstrip('/')
        DB_USER = _parsed.username
        DB_PASSWORD = _parsed.password
        DB_HOST = _parsed.hostname
        DB_PORT = _parsed.port or 5432
    else:
        DB_NAME = os.getenv('DB_NAME')
        DB_USER = os.getenv('DB_USER')
        DB_PASSWORD = os.getenv('DB_PASSWORD')
        DB_HOST = os.getenv('DB_HOST')
        DB_PORT = os.getenv('DB_PORT')

    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    # Необязательный — без него /chat показывает баннер "не настроено" вместо ошибки.
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 31536000

    @classmethod
    def validate(cls):
        required_vars = ['DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT', 'SECRET_KEY']
        missing = [v for v in required_vars if not getattr(cls, v)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return True
