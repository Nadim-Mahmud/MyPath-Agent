# Stage 1: Build the React app
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# VITE_API_BASE_URL is left empty so all API calls are relative (proxied by nginx)
ARG VITE_API_KEY
ENV VITE_API_BASE_URL=""
ENV VITE_API_KEY=${VITE_API_KEY}

RUN npm run build

# Stage 2: Development — Vite dev server with hot reload
# Polling env vars live here so they only apply to this stage, not production
FROM node:20-alpine AS development
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV CHOKIDAR_USEPOLLING=true
ENV WATCHPACK_POLLING=true
EXPOSE 80
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "80"]

# Stage 3: Production — nginx serving the built static files
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
