# ============================================================
# Этап 1: Сборка зависимостей
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Копируем только requirements.txt для кеширования слоя
COPY requirements.txt .

# Устанавливаем зависимости в отдельную директорию
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================
# Этап 2: Финальный образ
# ============================================================
FROM python:3.11-slim AS runtime

# Создаём непривилегированного пользователя
RUN groupadd -r appuser && useradd -r -g appuser -d /home/appuser -s /sbin/nologin appuser

WORKDIR /app

# Копируем установленные зависимости из builder
COPY --from=builder /install /usr/local

# Копируем исходный код приложения
COPY src/ ./src/

# Передаём владение файлов пользователю appuser
RUN chown -R appuser:appuser /app

# Переключаемся на непривилегированного пользователя
USER appuser

# Переменные окружения по умолчанию
# PYTHONPATH указывает Python искать модули начиная с папки src
ENV PORT=5000 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Открываем порт
EXPOSE 5000

# Запуск через gunicorn. 
# Благодаря PYTHONPATH=/app/src, модуль wsgi находится в корне пути поиска
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "wsgi:app"]