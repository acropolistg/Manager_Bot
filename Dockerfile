# Используем официальный Python образ
FROM python:3.9-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем зависимости
COPY requirements.txt /app/

# Устанавливаем зависимости
RUN pip install -r requirements.txt

# Копируем весь код в контейнер
COPY . /app/

# Указываем команду для запуска приложения
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:$PORT", "bot:app"]
