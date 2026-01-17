import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # База данных (ваши параметры Render)
    POSTGRES_HOST = 'dpg-d4im0jh5pdvs73834210-a.oregon-postgres.render.com'
    POSTGRES_PORT = '5432'
    POSTGRES_DB = 'alfa_collection'
    POSTGRES_USER = 'alfa_collection_user'
    POSTGRES_PASSWORD = 'VpjoxZ45dhe6wxXicJEHLMySD6og4loj'
    
    # Формируем URL для SQLAlchemy
    SQLALCHEMY_DATABASE_URI = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки пула соединений
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 30,
        'connect_args': {
            'connect_timeout': 10,
            'statement_timeout': 30000,  # 30 секунд
        }
    }
    
    # Безопасность
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Настройки Flask
    FLASK_ENV = os.environ.get('FLASK_ENV') or 'development'
    DEBUG = FLASK_ENV == 'development'
    
    # Кэширование
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300  # 5 минут
    
    # Админ
    ADMIN_USERNAME = 'admin'
    ADMIN_PASSWORD = 'admin123'
    
    # Настройки пагинации
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 1000