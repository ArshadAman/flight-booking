#!/usr/bin/env bash
# Run ON the VPS (Hestia/host nginx). Proxies portal subdomains → Next.js :3000
set -euo pipefail

CONF="/etc/nginx/conf.d/domains/portals.occ.services.conf"
CERT="/etc/letsencrypt/live/api.occ.services/fullchain.pem"
KEY="/etc/letsencrypt/live/api.occ.services/privkey.pem"

if [[ ! -f "$CERT" ]]; then
  echo "Missing cert $CERT — expand Let's Encrypt cert with portal SANs first."
  exit 1
fi

cat > "$CONF" <<NGINX
# Next.js multi-portal (superadmin / subadmin / agent / supplier / www)
server {
    listen 72.61.21.201:80;
    server_name www.occ.services occ.services superadmin.occ.services subadmin.occ.services agent.occ.services supplier.occ.services;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
        allow all;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 72.61.21.201:443 ssl;
    server_name www.occ.services occ.services superadmin.occ.services subadmin.occ.services agent.occ.services supplier.occ.services;
    http2 on;

    ssl_certificate     /etc/letsencrypt/live/api.occ.services/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.occ.services/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 120s;
        client_max_body_size 20M;
    }
}
NGINX

nginx -t
systemctl reload nginx
echo "Installed $CONF"