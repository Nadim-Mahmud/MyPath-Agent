# Stage 1: Build the React app
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .

# VITE_API_BASE_URL is left empty so all API calls are relative (proxied by nginx)
ARG VITE_API_KEY
ENV VITE_API_BASE_URL=""
ENV VITE_API_KEY=${VITE_API_KEY}

RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
