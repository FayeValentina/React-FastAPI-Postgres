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

# 生成 Cloudflare 出口 IP 列表到指定文件
generate_cf_ips_to() {
    OUTPUT_FILE="$1"
    TMP_BUILD_FILE="$(mktemp)"

    {
        echo "# Cloudflare IP addresses"
        echo "# Generated on $(date -u)"
        echo ""
        echo "# IPv4"
        if curl -fsSL https://www.cloudflare.com/ips-v4 >/dev/null 2>&1; then
            curl -fsSL https://www.cloudflare.com/ips-v4 | while read -r ip; do
                # 基础校验：IPv4/CIDR
                if echo "$ip" | grep -Eq '^[0-9]+(\.[0-9]+){3}/[0-9]+$'; then
                    echo "set_real_ip_from $ip;"
                fi
            done
        else
            echo "# (warn) failed to fetch IPv4 list"
        fi
        echo ""
        echo "# IPv6"
        if curl -fsSL https://www.cloudflare.com/ips-v6 >/dev/null 2>&1; then
            curl -fsSL https://www.cloudflare.com/ips-v6 | while read -r ip; do
                # 基础校验：IPv6/CIDR（宽松）
                if echo "$ip" | grep -Eq '^[0-9A-Fa-f:]+/[0-9]+$'; then
                    echo "set_real_ip_from $ip;"
                fi
            done
        else
            echo "# (warn) failed to fetch IPv6 list"
        fi
    } >"$TMP_BUILD_FILE"

    mv "$TMP_BUILD_FILE" "$OUTPUT_FILE"
}

# 动态更新 Cloudflare 出口 IP 列表，供 real_ip 使用（一次性）
update_cloudflare_ips() {
    CLOUDFLARE_CONF="/etc/nginx/conf.d/cloudflare_ips.conf"
    TMP_FILE="$(mktemp)"

    echo "🌐 获取 Cloudflare IP 列表..."
    # 确保容器具备拉取 HTTPS 的工具
    if ! command -v curl >/dev/null 2>&1; then
        echo "📦 安装 curl 与 CA 证书..."
        apk add --no-cache curl ca-certificates >/dev/null 2>&1 || true
    fi

    generate_cf_ips_to "$TMP_FILE"

    mkdir -p /etc/nginx/conf.d
    mv "$TMP_FILE" "$CLOUDFLARE_CONF"
    echo "✅ 已生成 $CLOUDFLARE_CONF"
}

# 在渲染模板与校验前执行更新，以确保 include 的文件存在
update_cloudflare_ips || echo "⚠️  Cloudflare IP 列表更新失败，将继续使用现有配置（若存在）"

# 后台定时刷新 Cloudflare IP 列表并必要时 reload Nginx
CF_IP_REFRESH_ENABLED="${CF_IP_REFRESH_ENABLED:-false}"
CF_IP_REFRESH_INTERVAL="${CF_IP_REFRESH_INTERVAL:-86400}"

start_cf_refresh_loop() {
    if [ "$CF_IP_REFRESH_ENABLED" = "true" ]; then
        echo "⏱️  启用 Cloudflare IP 定期刷新，间隔: ${CF_IP_REFRESH_INTERVAL}s"
        (
            while true; do
                sleep "$CF_IP_REFRESH_INTERVAL" || sleep 86400
                echo "🌐 定期刷新 Cloudflare IP 列表..."
                CLOUDFLARE_CONF="/etc/nginx/conf.d/cloudflare_ips.conf"
                TMP_FILE="$(mktemp)"

                # 若 curl 不存在则尝试安装
                if ! command -v curl >/dev/null 2>&1; then
                    apk add --no-cache curl ca-certificates >/dev/null 2>&1 || true
                fi

                generate_cf_ips_to "$TMP_FILE"

                # 若生成文件为空，跳过
                if [ ! -s "$TMP_FILE" ]; then
                    echo "⚠️  刷新失败：内容为空，保留现有配置"
                    rm -f "$TMP_FILE"
                    continue
                fi

                # 若无变化则跳过
                if [ -f "$CLOUDFLARE_CONF" ] && cmp -s "$TMP_FILE" "$CLOUDFLARE_CONF"; then
                    echo "ℹ️  列表无变化，跳过 reload"
                    rm -f "$TMP_FILE"
                    continue
                fi

                # 备份旧文件
                if [ -f "$CLOUDFLARE_CONF" ]; then
                    cp -f "$CLOUDFLARE_CONF" "${CLOUDFLARE_CONF}.bak" || true
                fi

                mv "$TMP_FILE" "$CLOUDFLARE_CONF"

                if nginx -t >/dev/null 2>&1; then
                    nginx -s reload && echo "✅ 已重载 Nginx（Cloudflare IP 更新）"
                else
                    echo "❌ 新配置校验失败，回滚旧版本"
                    if [ -f "${CLOUDFLARE_CONF}.bak" ]; then
                        mv "${CLOUDFLARE_CONF}.bak" "$CLOUDFLARE_CONF"
                    fi
                fi
            done
        ) &
    else
        echo "⏸️  未启用 Cloudflare IP 定期刷新"
    fi
}

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

# 启动后台定期刷新任务（如启用）
start_cf_refresh_loop

# 执行容器原始命令
exec "$@"
