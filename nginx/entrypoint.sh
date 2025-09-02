#!/bin/sh
# Nginx 配置动态生成脚本（根据环境变量渲染模板）
set -eu

echo "开始生成 Nginx 配置文件..."

TEMPLATE_DIR="/etc/nginx/templates"
CONFIG_DIR="/etc/nginx/conf.d"

# 检查关键环境变量（仅域名相关，避免污染 Nginx 内置变量）
required_vars="DOMAIN_MAIN SUBDOMAIN_PORTAINER SUBDOMAIN_PGADMIN SUBDOMAIN_REDIS"
for var in $required_vars; do
  eval "value=\${$var:-}"
  if [ -z "$value" ]; then
    echo "错误: 环境变量 $var 未设置" >&2
    exit 1
  fi
  echo "- $var=$value"
done

# 需要替换的变量列表（限制 envsubst 范围，保留 $host/$remote_addr 等）
VARS_TO_SUBSTITUTE='${DOMAIN_MAIN} ${SUBDOMAIN_PORTAINER} ${SUBDOMAIN_PGADMIN} ${SUBDOMAIN_REDIS}'

mkdir -p -- "$CONFIG_DIR"

if [ ! -d "$TEMPLATE_DIR" ]; then
  echo "错误: 模板目录 $TEMPLATE_DIR 不存在" >&2
  exit 1
fi

echo "渲染服务配置模板..."
find "$TEMPLATE_DIR" -maxdepth 1 -type f -name '*.template' -print0 |
while IFS= read -r -d '' template; do
  output_file="$CONFIG_DIR/$(basename "$template" .template)"
  envsubst "$VARS_TO_SUBSTITUTE" < "$template" > "$output_file"
  echo "生成: $output_file"
done

echo "渲染主配置模板..."
envsubst "$VARS_TO_SUBSTITUTE" < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

echo "验证 Nginx 配置..."
if nginx -t; then
  echo "配置验证成功"
else
  echo "配置验证失败，请检查模板与生成文件" >&2
  nginx -t || true
  exit 1
fi

echo "配置渲染完成，启动 Nginx..."
exec "$@"
