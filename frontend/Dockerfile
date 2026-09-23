FROM node:22.23.2-alpine3.23 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run check:api-types && npm run build && npm run check:bundle
FROM nginxinc/nginx-unprivileged:1.29.3-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
