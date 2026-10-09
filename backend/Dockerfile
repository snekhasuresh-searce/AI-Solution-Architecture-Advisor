# Backend API (Python). Build from this folder:
#   docker build -t advisor-backend .
#   docker run -p 8080:8080 --env-file .env advisor-backend
FROM python:3.12-slim
# DejaVu fonts give PDF exports full Unicode coverage (arrows, accents).
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn advisor.api:app --host 0.0.0.0 --port ${PORT}"]
