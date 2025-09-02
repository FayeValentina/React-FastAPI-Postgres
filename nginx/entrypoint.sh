#!/bin/sh
set -e

TEMPLATE_DIR="/etc/nginx/templates"
CONFIG_DIR="/etc/nginx/conf.d"

# ensure essential environment variables are present
required_vars="DOMAIN_MAIN SUBDOMAIN_PGADMIN SUBDOMAIN_REDIS SUBDOMAIN_PORTAINER"
for var in $required_vars; do
  if [ -z "${!var}" ]; then
    echo "Error: $var is not set." >&2
    exit 1
  fi
done

mkdir -p ${CONFIG_DIR}

if [ ! -d "${TEMPLATE_DIR}" ]; then
  echo "Template directory ${TEMPLATE_DIR} not found."
  exit 1
fi

echo "Rendering Nginx config files from environment variables..."
for template in $(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name "*.template"); do
  output_file="${CONFIG_DIR}/$(basename "${template}" .template)"
  envsubst < "${template}" > "${output_file}"
  echo "Generated: ${output_file}"
done

envsubst < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

echo "Configuration rendering complete."
exec "$@"

