FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html

# Nginx image already ships a HEALTHCHECK-friendly process; add an explicit
# one so `docker compose ps` reports frontend health accurately.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1

EXPOSE 80
