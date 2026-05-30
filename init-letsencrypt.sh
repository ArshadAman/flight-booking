#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

domains="api.occ.services"
rsa_key_size=4096
data_path="./data/certbot"
email="admin@occ.services" # Replace with your email address or leave blank for register-unsafely-without-email
staging=0 # Set to 1 if you're testing to avoid hitting Let's Encrypt rate limits

if [ -d "$data_path" ]; then
  read -p "Existing data found for $domains. Continue and replace existing certificates? (y/N) " decision
  if [ "$decision" != "Y" ] && [ "$decision" != "y" ]; then
    exit
  fi
fi

if [ ! -e "$data_path/conf/options-ssl-nginx.conf" ] || [ ! -e "$data_path/conf/ssl-dhparams.pem" ]; then
  echo "### Downloading recommended TLS parameters ..."
  mkdir -p "$data_path/conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "$data_path/conf/options-ssl-nginx.conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "$data_path/conf/ssl-dhparams.pem"
  echo
fi

echo "### Creating robust 10-year self-signed fallback certificate for $domains ..."
path="/etc/letsencrypt/live/$domains"
docker compose run --entrypoint \
  "sh -c 'mkdir -p /etc/letsencrypt/live/$domains && openssl req -x509 -nodes -newkey rsa:$rsa_key_size -days 3650 -keyout "$path/privkey.pem" -out "$path/fullchain.pem" -subj \"/CN=$domains\"'" certbot
echo

echo "### Starting all containers (Nginx, Django, DB, Redis) ..."
docker compose up -d
echo

echo "### Requesting Let's Encrypt certificate for $domains ..."
# Join $domains to comma-separated string
domain_args=""
for domain in $domains; do
  domain_args="$domain_args -d $domain"
done


# Select appropriate email arg
email_arg="--register-unsafely-without-email"
if [ -n "$email" ]; then
  email_arg="--email $email"
fi

# Enable staging mode if needed
staging_arg=""
if [ $staging -ne 0 ]; then
  staging_arg="--staging"
fi

# Try to request the certificate. If it fails, keep the self-signed fallback.
set +e
docker compose run --entrypoint \
  "certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    $email_arg \
    $domain_args \
    --rsa-key-size $rsa_key_size \
    --agree-tos \
    --force-renewal \
    --non-interactive" certbot
certbot_status=$?
set -e

if [ $certbot_status -ne 0 ]; then
  echo "========================================================================="
  echo "WARNING: Certbot failed to obtain a real SSL certificate (likely due to DNS/CNAME issues)."
  echo "FALLBACK: Preserving the 10-year self-signed certificate."
  echo "Your application is ONLINE over HTTPS, but browsers will show a warning"
  echo "until the DNS issues are resolved and you rerun this script."
  echo "========================================================================="
else
  echo "========================================================================="
  echo "SUCCESS: Obtained real Let's Encrypt certificate!"
  echo "### Reloading nginx ..."
  docker compose exec nginx nginx -s reload
  echo "========================================================================="
fi

