# Используем Python 3.9 как базовый образ
FROM python:3.9-slim

# Установим рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем всё содержимое вашего проекта в контейнер
COPY . .

# Открываем порт, который будет слушать приложение
EXPOSE 8080

# Запускаем приложение через Python
CMD ["python", "app.py"]
