# ---------- Build stage ----------
FROM node:20-bookworm AS build

WORKDIR /app

# OPTIMIZATION: Only copy package.json.
# We intentionally skip package-lock.json so we don't bring in Windows-specific dependency trees.
COPY package.json ./

# 'npm install' will now generate a fresh, correct lockfile for Linux automatically.
RUN npm install

COPY . .
RUN npm run build

# ---------- Runtime stage ----------
FROM nginx:alpine

# Inline nginx SPA configuration
RUN printf '%s\n' \
  'server {' \
  '  listen 80;' \
  '  server_name _;' \
  '' \
  '  root /usr/share/nginx/html;' \
  '  index index.html;' \
  '' \
  '  location / {' \
  '    try_files $uri $uri/ /index.html;' \
  '  }' \
  '}' \
  > /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80