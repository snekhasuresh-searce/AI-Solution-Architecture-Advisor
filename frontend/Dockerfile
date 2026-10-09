# Frontend (React + TypeScript), served by nginx. Build from this folder:
#   docker build -t advisor-frontend .
#   docker run -p 8000:80 -e BACKEND_URL=http://host.docker.internal:8080 advisor-frontend
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
ENV PORT=80 BACKEND_URL=http://backend:8080
# nginx substitutes only these, leaving its own $host / $uri alone.
ENV NGINX_ENVSUBST_FILTER="^(PORT|BACKEND_URL)$"
EXPOSE 80
