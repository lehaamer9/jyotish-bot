FROM python:3.12-slim

# Установка рабочей директории
WORKDIR /app

# Установка системных зависимостей для сборки (если потребуются)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Установка Python-библиотек
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код бота
COPY . .

# Команда запуска
CMD ["python", "bot.py"]

