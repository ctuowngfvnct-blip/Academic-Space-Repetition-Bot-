FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py database.py ./

# DB sẽ nằm trong persistent volume mount tại /data
ENV DB_PATH=/data/srbot.db

CMD ["python", "bot.py"]
