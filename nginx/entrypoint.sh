#!/bin/sh
# Nginx 配置动态生成脚本（根据环境变量渲染模板）
set -e

echo "🔧 开始生成 Nginx 配置文件..."

# 检查关键环境变量
required_vars="DOMAIN_MAIN SUBDOMAIN_PORTAINER SUBDOMAIN_PGADMIN SUBDOMAIN_REDIS"
for var in $required_vars; do
    eval value=\$$var
    if [ -z "$value" ]; then
        echo "❌ 错误: 环境变量 $var 未设置"
        exit 1
    fi
    echo "✅ $var = $value"
done

# 生成 IP 访问限制块
if [ "$ENABLE_IP_RESTRICTION" = "true" ]; then
    echo "🔒 启用 IP 访问限制"
    IP_RESTRICTION_BLOCK=""

    if [ -n "$ALLOWED_IP_HOME" ]; then
        IP_RESTRICTION_BLOCK="${IP_RESTRICTION_BLOCK}        allow $ALLOWED_IP_HOME;
"
        echo "   ✅ 允许家庭 IP: $ALLOWED_IP_HOME"
    fi

    if [ -n "$ALLOWED_IP_OFFICE" ]; then
        IP_RESTRICTION_BLOCK="${IP_RESTRICTION_BLOCK}        allow $ALLOWED_IP_OFFICE;
"
        echo "   ✅ 允许办公 IP: $ALLOWED_IP_OFFICE"
    fi

    if [ -n "$IP_RESTRICTION_BLOCK" ]; then
        IP_RESTRICTION_BLOCK="${IP_RESTRICTION_BLOCK}        deny all;
"
    else
        echo "⚠️  警告: 启用了 IP 限制但未设置任何允许的 IP"
    fi
else
    echo "🔓 IP 访问限制已禁用"
    IP_RESTRICTION_BLOCK=""
fi

export IP_RESTRICTION_BLOCK

# 需要替换的变量列表（避免污染 Nginx 内置变量）
VARS_TO_SUBSTITUTE='$DOMAIN_MAIN $SUBDOMAIN_PORTAINER $SUBDOMAIN_PGADMIN $SUBDOMAIN_REDIS $IP_RESTRICTION_BLOCK'

# 渲染主配置
MAIN_TEMPLATE="/etc/nginx/nginx.conf.template"
MAIN_CONFIG="/etc/nginx/nginx.conf"

if [ -f "$MAIN_TEMPLATE" ]; then
    echo "📝 生成主配置: nginx.conf"
    envsubst "$VARS_TO_SUBSTITUTE" < "$MAIN_TEMPLATE" > "$MAIN_CONFIG"
else
    echo "❌ 错误: 主配置模板 $MAIN_TEMPLATE 不存在"
    exit 1
fi

# 渲染服务配置模板
TEMPLATE_DIR="/etc/nginx/templates"
CONFIG_DIR="/etc/nginx/conf.d"

if [ -d "$TEMPLATE_DIR" ]; then
    echo "📁 处理服务配置模板..."
    for template_file in "$TEMPLATE_DIR"/*.template; do
        if [ -f "$template_file" ]; then
            config_name=$(basename "$template_file" .template)
            echo "   ✅ 生成 $config_name"
            envsubst "$VARS_TO_SUBSTITUTE" < "$template_file" > "$CONFIG_DIR/$config_name"
        fi
    done
else
    echo "⚠️  警告: 模板目录 $TEMPLATE_DIR 不存在，跳过服务配置生成"
fi

# 简单的配置验证
echo "🔍 验证 Nginx 配置..."
if nginx -t 2>/dev/null; then
    echo "✅ 配置验证成功"
else
    echo "❌ 配置验证失败，请检查模板文件"
    nginx -t
    exit 1
fi

echo "🎉 配置生成完成，启动 Nginx..."

# 执行容器原始命令
exec "$@"
