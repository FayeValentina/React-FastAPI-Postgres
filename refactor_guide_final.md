# Web应用完整重构指南 - 整合版

## 🎯 **重构目标**
- ✅ 添加 Portainer 容器管理功能
- ✅ 通过子域名安全访问所有管理工具
- ✅ 实现配置完全动态化，支持任意环境部署
- ✅ 敏感信息与代码完全分离
- ✅ 符合 Docker 最佳实践

## 📋 **完整实施步骤**

### **第1步：重构目录结构**

```bash
# 创建新的目录结构
mkdir -p nginx/conf/dev
mkdir -p nginx/conf/prod

# 迁移现有配置文件
mv nginx/conf.d/common-locations-dev.conf nginx/conf/dev/
mv nginx/conf.d/common-locations-prod.conf nginx/conf/prod/

# 删除旧目录
rm -rf nginx/conf.d
```

**最终目录结构：**
```
nginx/
├── conf/
│   ├── dev/
│   │   └── common-locations-dev.conf
│   └── prod/
│       ├── common-locations-prod.conf.template
│       ├── portainer.conf.template
│       ├── pgadmin.conf.template
│       └── redisinsight.conf.template
├── ssl/
├── nginx.dev.conf
├── nginx.prod.conf.template
└── entrypoint.sh
```

### **第2步：创建动态配置脚本**

创建 `nginx/entrypoint.sh`：

```bash
#!/bin/sh
# Nginx配置动态生成脚本
set -e

echo "🔧 开始生成Nginx配置文件..."

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

# 生成IP访问限制块
if [ "$ENABLE_IP_RESTRICTION" = "true" ]; then
    echo "🔒 启用IP访问限制"
    IP_RESTRICTION_BLOCK=""
    
    if [ -n "$ALLOWED_IP_HOME" ]; then
        IP_RESTRICTION_BLOCK="$IP_RESTRICTION_BLOCK        allow $ALLOWED_IP_HOME;\n"
        echo "   ✅ 允许家庭IP: $ALLOWED_IP_HOME"
    fi
    
    if [ -n "$ALLOWED_IP_OFFICE" ]; then
        IP_RESTRICTION_BLOCK="$IP_RESTRICTION_BLOCK        allow $ALLOWED_IP_OFFICE;\n"
        echo "   ✅ 允许办公IP: $ALLOWED_IP_OFFICE"
    fi
    
    if [ -n "$IP_RESTRICTION_BLOCK" ]; then
        IP_RESTRICTION_BLOCK="$IP_RESTRICTION_BLOCK        deny all;"
    else
        echo "⚠️  警告: 启用了IP限制但未设置任何允许的IP"
    fi
else
    echo "🔓 IP访问限制已禁用"
    IP_RESTRICTION_BLOCK=""
fi

export IP_RESTRICTION_BLOCK

# 定义要替换的变量
VARS_TO_SUBSTITUTE='$DOMAIN_MAIN $SUBDOMAIN_PORTAINER $SUBDOMAIN_PGADMIN $SUBDOMAIN_REDIS $IP_RESTRICTION_BLOCK'

# 处理主配置文件
MAIN_TEMPLATE="/etc/nginx/nginx.conf.template"
MAIN_CONFIG="/etc/nginx/nginx.conf"

if [ -f "$MAIN_TEMPLATE" ]; then
    echo "📝 生成主配置: nginx.conf"
    envsubst "$VARS_TO_SUBSTITUTE" < "$MAIN_TEMPLATE" > "$MAIN_CONFIG"
else
    echo "❌ 错误: 主配置模板 $MAIN_TEMPLATE 不存在"
    exit 1
fi

# 处理服务配置文件
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

# 验证配置
echo "🔍 验证Nginx配置..."
if nginx -t 2>/dev/null; then
    echo "✅ 配置验证成功"
else
    echo "❌ 配置验证失败"
    nginx -t
    exit 1
fi

echo "🎉 配置生成完成，启动Nginx..."
exec "$@"
```

```bash
# 设置执行权限
chmod +x nginx/entrypoint.sh
```

### **第3步：创建配置模板文件**

#### **3.1 主配置模板 `nginx/nginx.prod.conf.template`**

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 2048;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # 日志格式
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    # 性能优化
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 4096;
    server_tokens off;
    client_max_body_size 100M;
    client_body_buffer_size 128k;

    # 速率限制
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
    limit_req_zone $binary_remote_addr zone=admin:10m rate=2r/m;
    limit_req_zone $binary_remote_addr zone=portainer:10m rate=5r/m;
    
    # Gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;

    # SSL全局配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_session_tickets off;

    upstream backend {
        server backend:8000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    # HTTP -> HTTPS 统一重定向
    server {
        listen 80;
        server_name ${DOMAIN_MAIN}
                    ${SUBDOMAIN_PORTAINER}.${DOMAIN_MAIN}
                    ${SUBDOMAIN_PGADMIN}.${DOMAIN_MAIN}
                    ${SUBDOMAIN_REDIS}.${DOMAIN_MAIN};
        return 301 https://$server_name$request_uri;
    }

    # 主应用 HTTPS 服务器配置
    server {
        listen 443 ssl http2;
        server_name ${DOMAIN_MAIN};
        
        ssl_certificate /etc/nginx/ssl/${DOMAIN_MAIN}.pem;
        ssl_certificate_key /etc/nginx/ssl/${DOMAIN_MAIN}.key;
        
        include /etc/nginx/conf.d/common-locations-prod.conf;
    }

    # 包含管理工具的服务器配置
    include /etc/nginx/conf.d/pgadmin.conf;
    include /etc/nginx/conf.d/portainer.conf;
    include /etc/nginx/conf.d/redisinsight.conf;
}
```

#### **3.2 转换现有配置为模板**

```bash
# 转换主应用配置
mv nginx/conf/prod/common-locations-prod.conf nginx/conf/prod/common-locations-prod.conf.template
```

#### **3.3 创建管理工具配置模板**

**`nginx/conf/prod/portainer.conf.template`**
```nginx
# Portainer 反向代理配置
upstream portainer {
    server portainer:9000 max_fails=3 fail_timeout=30s;
    keepalive 8;
}

server {
    listen 443 ssl http2;
    server_name ${SUBDOMAIN_PORTAINER}.${DOMAIN_MAIN};
    
    ssl_certificate /etc/nginx/ssl/${DOMAIN_MAIN}.pem;
    ssl_certificate_key /etc/nginx/ssl/${DOMAIN_MAIN}.key;
    
    # SSL安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # 安全头部
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    limit_req zone=portainer burst=20 nodelay;
    
    location / {
        ${IP_RESTRICTION_BLOCK}
        
        proxy_pass http://portainer;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
        
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_cache off;
    }
    
    location /api/system/status {
        proxy_pass http://portainer;
        proxy_set_header Host $host;
        access_log off;
    }
}
```

**`nginx/conf/prod/pgadmin.conf.template`**
```nginx
# PgAdmin 反向代理配置
upstream pgadmin {
    server pgadmin:80 max_fails=3 fail_timeout=30s;
    keepalive 8;
}

server {
    listen 443 ssl http2;
    server_name ${SUBDOMAIN_PGADMIN}.${DOMAIN_MAIN};
    
    ssl_certificate /etc/nginx/ssl/${DOMAIN_MAIN}.pem;
    ssl_certificate_key /etc/nginx/ssl/${DOMAIN_MAIN}.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;" always;
    
    limit_req zone=admin burst=10 nodelay;
    
    location / {
        ${IP_RESTRICTION_BLOCK}
        
        proxy_pass http://pgadmin;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_set_header X-Script-Name "";
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_cache off;
    }
    
    location /misc/ping {
        proxy_pass http://pgadmin;
        proxy_set_header Host $host;
        access_log off;
    }
}
```

**`nginx/conf/prod/redisinsight.conf.template`**
```nginx
# RedisInsight 反向代理配置
upstream redisinsight {
    server redisinsight:5540 max_fails=3 fail_timeout=30s;
    keepalive 8;
}

server {
    listen 443 ssl http2;
    server_name ${SUBDOMAIN_REDIS}.${DOMAIN_MAIN};
    
    ssl_certificate /etc/nginx/ssl/${DOMAIN_MAIN}.pem;
    ssl_certificate_key /etc/nginx/ssl/${DOMAIN_MAIN}.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self' wss:;" always;
    
    limit_req zone=admin burst=10 nodelay;
    
    location / {
        ${IP_RESTRICTION_BLOCK}
        
        proxy_pass http://redisinsight;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
        
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_cache off;
    }
    
    location /healthcheck/ {
        proxy_pass http://redisinsight;
        proxy_set_header Host $host;
        access_log off;
    }
}
```

### **第4步：更新Docker Compose文件**

#### **4.1 更新 `docker-compose.prod.yml`**

```yaml
services:
  # nginx 反向代理服务
  nginx:
    image: nginx:alpine
    container_name: nginx_proxy_prod
    env_file:
      - .env.prod
    ports:
      - "80:80"
      - "443:443"
    volumes:
      # 主配置模板
      - ./nginx/nginx.prod.conf.template:/etc/nginx/nginx.conf.template:ro
      # 服务配置模板目录
      - ./nginx/conf/prod:/etc/nginx/templates:ro
      # 启动脚本
      - ./nginx/entrypoint.sh:/entrypoint.sh:ro
      # SSL证书和静态文件
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - frontend_build:/usr/share/nginx/html:ro
      # 日志目录
      - prod_nginx_logs:/var/log/nginx
    depends_on:
      - frontend_builder
      - backend
      - portainer
      - pgadmin
      - redisinsight
    networks:
      - prodNetWork
    # 使用自定义entrypoint脚本
    entrypoint: ["/entrypoint.sh"]
    command: ["nginx", "-g", "daemon off;"]
    healthcheck:
      test: ["CMD", "nginx", "-t"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    mem_limit: 128M
    mem_reservation: 64M

  # 前端构建服务 - 只用于构建静态文件
  frontend_builder:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
      args:
        - NODE_ENV=production
        - VITE_API_URL=${FRONTEND_URL}/api
    env_file:
      - .env.prod
    volumes:
      - frontend_build:/app/dist
    networks:
      - prodNetWork

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    env_file:
      - .env.prod
    expose:
      - "8000"
    environment:
      - POSTGRES_HOST=${POSTGRES_HOST}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
      - SECRET_KEY=${SECRET_KEY}
      - ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES}
      - RABBITMQ_HOST=${RABBITMQ_HOST}
      - RABBITMQ_USER=${RABBITMQ_USER}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}
      - REDIS_HOST=${REDIS_HOST}
      - REDIS_PORT=${REDIS_PORT}
      - REDIS_DB=${REDIS_DB}
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: >
      bash -c "
        echo '等待数据库准备...' &&
        echo '应用数据库迁移...' &&
        poetry run alembic upgrade head &&
        echo '启动生产服务器...' &&
        poetry run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --access-logfile - --error-logfile -
      "
    networks:
      - prodNetWork
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    mem_limit: 1G
    mem_reservation: 512M

  postgres:
    image: postgres:17
    env_file:
      - .env.prod
    expose:
      - "5432"
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - prod_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - prodNetWork
    restart: unless-stopped
    mem_limit: 1G
    mem_reservation: 512M

  pgadmin:
    image: dpage/pgadmin4:8.8
    container_name: pgadmin_prod
    env_file:
      - .env.prod
    expose:
      - "80"
    environment:
      - PGADMIN_DEFAULT_EMAIL=${PGADMIN_DEFAULT_EMAIL}
      - PGADMIN_DEFAULT_PASSWORD=${PGADMIN_DEFAULT_PASSWORD}
      - PGADMIN_CONFIG_SERVER_MODE=${PGADMIN_CONFIG_SERVER_MODE}
      - PGADMIN_CONFIG_ENHANCED_COOKIE_PROTECTION=${PGADMIN_CONFIG_ENHANCED_COOKIE_PROTECTION}
      - PGADMIN_CONFIG_WTF_CSRF_ENABLED=${PGADMIN_CONFIG_WTF_CSRF_ENABLED}
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - prodNetWork
    restart: unless-stopped
    mem_limit: 256M
    mem_reservation: 128M
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost/misc/ping || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  rabbitmq:
    image: rabbitmq:4-management
    env_file:
      - .env.prod
    expose:
      - "5672"
    ports:
      - "127.0.0.1:${RABBITMQ_PLUGIN_PORT}:15672"
    environment:
      - RABBITMQ_DEFAULT_USER=${RABBITMQ_USER}
      - RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD}
      - RABBITMQ_DEFAULT_VHOST=${RABBITMQ_VHOST}
    volumes:
      - prod_rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - prodNetWork
    restart: unless-stopped
    mem_limit: 512M
    mem_reservation: 256M

  redis:
    image: redis:7-alpine
    env_file:
      - .env.prod
    expose:
      - "6379"
    volumes:
      - prod_redis_data:/data
    command: >
      sh -c "
        redis-server --requirepass '${REDIS_PASSWORD}' --appendonly yes --maxmemory 320mb --maxmemory-policy allkeys-lru
      "
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 30s
      timeout: 5s
      retries: 5
    networks:
      - prodNetWork
    restart: unless-stopped
    mem_limit: 384M
    mem_reservation: 256M

  redisinsight:
    image: redislabs/redisinsight:2.70.0
    container_name: redisinsight_prod
    env_file:
      - .env.prod
    expose:
      - "5540"
    volumes:
      - prod_redisinsight_data:/db
    environment:
      - RITRUSTEDORIGINS=https://${SUBDOMAIN_REDIS}.${DOMAIN_MAIN}
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - prodNetWork
    mem_limit: 256M
    mem_reservation: 128M
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:5540/healthcheck/ || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  portainer:
    image: portainer/portainer-ce:2.27.9-alpine
    container_name: portainer_prod
    expose:
      - "9000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - prod_portainer_data:/data
    networks:
      - prodNetWork
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9000/api/system/status || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    mem_limit: 256M
    mem_reservation: 128M

  taskiq_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    env_file:
      - .env.prod
    environment:
      - POSTGRES_HOST=${POSTGRES_HOST}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
      - RABBITMQ_HOST=${RABBITMQ_HOST}
      - RABBITMQ_USER=${RABBITMQ_USER}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}
      - RABBITMQ_DEFAULT_VHOST=${RABBITMQ_VHOST}
      - REDIS_HOST=${REDIS_HOST}
      - REDIS_PORT=${REDIS_PORT}
      - REDIS_DB=${REDIS_DB}
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: >
      bash -c "
        echo '等待依赖服务...' &&
        sleep 15 &&
        poetry run taskiq worker --fs-discover --tasks-pattern 'app/tasks/*.py' app.broker:broker --log-level ${LOG_LEVEL:-WARNING}
      "
    networks:
      - prodNetWork
    healthcheck:
      test: ["CMD", "pgrep", "-f", "taskiq worker"]
      interval: 60s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    scale: ${TASKIQ_WORKER_CONCURRENCY:-2}
    mem_limit: 512M
    mem_reservation: 256M

  taskiq_scheduler:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    env_file:
      - .env.prod
    environment:
      - POSTGRES_HOST=${POSTGRES_HOST}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
      - RABBITMQ_HOST=${RABBITMQ_HOST}
      - RABBITMQ_USER=${RABBITMQ_USER}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}
      - RABBITMQ_DEFAULT_VHOST=${RABBITMQ_VHOST}
      - REDIS_HOST=${REDIS_HOST}
      - REDIS_PORT=${REDIS_PORT}
      - REDIS_DB=${REDIS_DB}
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      redis:
        condition: service_healthy
      taskiq_worker:
        condition: service_started
    command: >
      bash -c "
        echo '等待依赖服务...' &&
        sleep 20 &&
        poetry run taskiq scheduler app.broker:scheduler --log-level ${LOG_LEVEL:-WARNING}
      "
    networks:
      - prodNetWork
    healthcheck:
      test: ["CMD", "pgrep", "-f", "taskiq scheduler"]
      interval: 60s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    mem_limit: 256M
    mem_reservation: 128M

volumes:
  prod_postgres_data:
    driver: local
  prod_rabbitmq_data:
    driver: local
  prod_redis_data:
    driver: local
  prod_redisinsight_data:
    driver: local
  prod_portainer_data:
    driver: local
  prod_nginx_logs:
    driver: local
  frontend_build:
    driver: local

networks:
  prodNetWork:
    driver: bridge
```

#### **4.2 更新 `docker-compose.dev.yml`**

在开发环境的nginx服务中更新volume挂载：

```yaml
  nginx:
    image: nginx:alpine
    container_name: nginx_proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.dev.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf/dev:/etc/nginx/conf.d:ro  # 更新为新路径
      - dev_nginx_logs:/var/log/nginx
    depends_on:
      - frontend
      - backend
```

### **第5步：配置环境变量**

创建 `.env.prod.example`：

```env
# =================================
# 生产环境配置文件
# 复制此文件为 .env.prod 并填入真实值
# =================================

# === 应用基础配置 ===
ENVIRONMENT=production
PROJECT_NAME="FastAPI Backend"
VERSION="1.0.0"

# === 数据库配置 ===
POSTGRES_HOST=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_strong_password_here
POSTGRES_DB=postgres
POSTGRES_PORT=5432

# === 安全配置 ===
SECRET_KEY=your-super-secret-key-here-min-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256

# === 服务端口配置 ===
BACKEND_PORT=8000
FRONTEND_PORT=3000

# === Redis配置 ===
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password_here
REDIS_DB=0

# === RabbitMQ配置 ===
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=your_rabbit_user
RABBITMQ_PASSWORD=your_rabbit_password
RABBITMQ_VHOST=/
RABBITMQ_PLUGIN_PORT=15672

# === TaskIQ配置 ===
TASKIQ_WORKER_CONCURRENCY=2
LOG_LEVEL=WARNING

# === 管理工具配置 ===
PGADMIN_DEFAULT_EMAIL=admin@yourdomain.com
PGADMIN_DEFAULT_PASSWORD=your_pgadmin_password
PGADMIN_CONFIG_SERVER_MODE=True
PGADMIN_CONFIG_ENHANCED_COOKIE_PROTECTION=True
PGADMIN_CONFIG_WTF_CSRF_ENABLED=True

# =================================
# 🔥 动态配置核心变量 🔥
# =================================

# === 域名配置 ===
DOMAIN_MAIN=yourdomain.com
SUBDOMAIN_PORTAINER=portainer
SUBDOMAIN_PGADMIN=pgadmin
SUBDOMAIN_REDIS=redis

# === IP访问控制配置 ===
ENABLE_IP_RESTRICTION=true
ALLOWED_IP_HOME=203.0.113.100
ALLOWED_IP_OFFICE=198.51.100.50

# === 前端URL配置 ===
FRONTEND_URL=https://yourdomain.com
```

### **第6步：更新.gitignore**

```bash
# 环境变量文件
.env
.env.prod
.env.local
.env.*.local
```

## 🚀 **部署流程**

### **1. 部署前准备**

```bash
# 停止现有服务
docker-compose -f docker-compose.prod.yml down

# 配置环境变量
cp .env.prod.example .env.prod
nano .env.prod  # 修改为你的真实配置

# 确保SSL证书文件名正确
ls nginx/ssl/  # 应该有 yourdomain.com.pem 和 yourdomain.com.key
```

### **2. 配置DNS解析**

在DNS提供商添加以下记录：
```
yourdomain.com          -> 服务器IP
portainer.yourdomain.com -> 服务器IP
pgadmin.yourdomain.com  -> 服务器IP
redis.yourdomain.com    -> 服务器IP
```

### **3. 执行部署**

```bash
# 构建并启动服务
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 查看启动日志
docker-compose -f docker-compose.prod.yml logs -f nginx

# 检查服务状态
docker-compose -f docker-compose.prod.yml ps
```

### **4. 验证部署**

```bash
# 测试所有域名访问
curl -I https://yourdomain.com
curl -I https://portainer.yourdomain.com
curl -I https://pgadmin.yourdomain.com
curl -I https://redis.yourdomain.com

# 检查容器健康状态
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## 🎉 **部署完成**

成功部署后，你可以通过以下地址访问：

- 🏠 **主应用**: https://yourdomain.com
- 🐳 **容器管理**: https://portainer.yourdomain.com
- 🗄️ **数据库管理**: https://pgadmin.yourdomain.com
- 🔄 **Redis监控**: https://redis.yourdomain.com

## 🔒 **安全特性**

- ✅ 强制HTTPS访问，HTTP自动重定向
- ✅ 基于环境变量的IP白名单访问控制
- ✅ 完善的安全头部配置
- ✅ 不同服务的差异化速率限制
- ✅ 敏感信息与代码完全分离

## 🛠️ **故障排除**

如果遇到问题，可以检查：

```bash
# 检查nginx配置
docker exec nginx_proxy_prod nginx -t

# 查看nginx错误日志
docker-compose -f docker-compose.prod.yml logs nginx

# 检查模板替换结果
docker exec nginx_proxy_prod cat /etc/nginx/nginx.conf
```
