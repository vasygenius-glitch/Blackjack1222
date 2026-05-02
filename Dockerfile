FROM python:3.11-slim

# Устанавливаем необходимые пакеты для сети и сертификатов,
# чтобы улучшить связь с api.telegram.org на Hugging Face
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую папку
WORKDIR /app

# Копируем список зависимостей
COPY requirements.txt .

# Ставим либы (Firebase, Flask, aiogram и т.д.)
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы бота
COPY . .

# Открываем порт для Flask (стандарт HF)
EXPOSE 7860

# Запуск
CMD ["python", "main.py"]