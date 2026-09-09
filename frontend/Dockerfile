# Contexto de build = raiz do projeto (precisa alcançar deploy/nginx/vouchers.conf)

FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./

# Viram VITE_* embutidas no bundle em tempo de build (ver docker-compose.yml).
ARG VITE_API_BASE=""
ARG VITE_KIOSK_API_KEY=""
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_KIOSK_API_KEY=$VITE_KIOSK_API_KEY
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx/vouchers.conf /etc/nginx/conf.d/default.conf
