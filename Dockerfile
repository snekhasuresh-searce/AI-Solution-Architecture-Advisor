# Runs the advisor web UI. Works locally today and on Cloud Run later:
#   docker build -t solution-advisor .
#   docker run -p 8000:8000 --env-file .env solution-advisor
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "adk web --host 0.0.0.0 --port ${PORT} ."]
