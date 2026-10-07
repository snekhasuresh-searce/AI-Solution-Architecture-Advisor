# Advisor web app (React UI + API) in one container. Works locally and on Cloud Run:
#   docker build -t solution-advisor .
#   docker run -p 8000:8000 --env-file .env solution-advisor     -> http://localhost:8000

# 1. Build the React app
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 2. Python API, which also serves the built app
FROM python:3.12-slim
# DejaVu fonts give PDF exports full Unicode coverage (arrows, accents).
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=web /web/dist ./web/dist

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn advisor.api:app --host 0.0.0.0 --port ${PORT}"]
