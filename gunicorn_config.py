import multiprocessing
import os

# Количество воркеров
workers = min(4, multiprocessing.cpu_count() * 2 + 1)

# Настройки воркеров
worker_class = 'sync'
threads = 1

# Таймауты
timeout = 120
graceful_timeout = 30
keepalive = 2

# Логирование
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Ограничение памяти
max_requests = 1000
max_requests_jitter = 50

# Бинд
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# Preload для экономии памяти
preload_app = True