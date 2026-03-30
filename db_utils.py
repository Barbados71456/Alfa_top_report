# db_utils.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db():
    """Получить подключение к базе данных"""
    DB_CONFIG = {
        'host': os.environ.get('POSTGRES_HOST'),
        'port': os.environ.get('POSTGRES_PORT', '5432'),
        'dbname': os.environ.get('POSTGRES_DB'),
        'user': os.environ.get('POSTGRES_USER'),
        'password': os.environ.get('POSTGRES_PASSWORD')
    }
    
    try:
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Ошибка подключения к БД: {e}")
        raise