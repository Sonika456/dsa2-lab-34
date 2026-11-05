FROM python:3.11-slim AS builder

# Создаём внутри контейнера рабочую папку /install
WORKDIR /install

COPY requirements.txt .

# Устанавливаем библиотеки в папку /install
RUN pip install --prefix=/install -r requirements.txt

FROM python:3.11-slim

# Создаём рабочую папку /app для кода
WORKDIR /app

# Копируем установленные библиотеки
# Папку /install переносим в /usr/local
COPY --from=builder /install /usr/local

# Копируем весь код в текущую папку /app
COPY . .

# Указываем, что внутри контейнера приложение будет слушать порт 5000
EXPOSE 5000

# Указываем команду запуска приложения через gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

