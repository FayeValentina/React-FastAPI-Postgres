# Web应用重构指南 (最终版) - 动态配置通用方案

## 🎯 **重构目标**

将Web应用从**静态硬编码配置**升级为**动态模板化配置**，实现：
- ✅ 敏感信息（域名、IP）不暴露在代码中
- ✅ 通过子域名安全访问管理工具（Portainer、PgAdmin、RedisInsight）
- ✅ 配置高度通用化，任何人都可轻松部署
- ✅ 符合Docker最佳实践的容器化部署

## 📋 **实施步骤**

### **第1步：创建Nginx启动脚本**

在项目根目录的 `nginx/` 文件夹下创建 `entrypoint.sh`：
```bash
#!/bin/sh
# Nginx配置动态生成脚本 - 最终版
# 基于环境变量动态生成nginx配置文件

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
    
    # 添加允许的IP
    if [ -n "$ALLOWED_IP_HOME" ]; then
        IP_RESTRICTION_BLOCK="$IP_RESTRICTION_BLOCK        allow $ALLOWED_IP_HOME;\n"
        echo "   ✅ 允许家庭IP: $ALLOWED_IP_HOME"
    fi
    
    if [ -n "$ALLOWED_IP_OFFICE" ]; then
        IP_RESTRICTION_BLOCK="$IP_RESTRICTION_BLOCK        allow $ALLOWED_IP_OFFICE;\n"
        echo "   ✅ 允许办公IP: $ALLOWED_IP_OFFICE"
    fi
    
    # 添加deny all
    if [ -n "$IP_RESTRICTION_BLOCK" ]; then
        IP_RESTRICTION_BLOCK="$IP_RESTRICTION_BLOCK        deny all;"
    else
        echo "⚠️  警告: 启用了IP限制但未设置任何允许的IP"
    fi
else
    echo "🔓 IP访问限制已禁用"
    IP_RESTRICTION_BLOCK=""
fi

# 导出IP限制块供envsubst使用
export IP_RESTRICTION_BLOCK

# 定义要替换的变量（防止误替换nginx内置变量）
VARS_TO_SUBSTITUTE='$ALLOWED_IP_HOME $ALLOWED_IP_OFFICE $DOMAIN_MAIN $SUBDOMAIN_PORTAINER $SUBDOMAIN_PGADMIN $SUBDOMAIN_REDIS $IP_RESTRICTION_BLOCK'

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

# 简单的配置验证
echo "🔍 验证Nginx配置..."
if nginx -t 2>/dev/null; then
    echo "✅ 配置验证成功"
else
    echo "❌ 配置验证失败，请检查模板文件"
    # 显示详细错误信息用于调试
    nginx -t
    exit 1
fi

echo "🎉 配置生成完成，启动Nginx..."

# 执行Docker容器的原始命令
exec "$@"
```

**创建文件后，设置执行权限：**
```bash
chmod +x nginx/entrypoint.sh
```

### **第2步：创建主配置模板**

将现有的 `nginx/nginx.prod.conf` 转换为模板文件：
重命名为以下模板文件nginx/nginx.prod.conf.template

#### **nginx.prod.conf.template**
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

    # HTTP -> HTTPS 统一重定向 (使用环境变量)
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
        
        # 包含主应用的location配置
        include /etc/nginx/conf.d/common-locations-prod.conf;
    }

    # 包含管理工具的服务器配置
    include /etc/nginx/conf.d/pgadmin.conf;
    include /etc/nginx/conf.d/portainer.conf;
    include /etc/nginx/conf.d/redisinsight.conf;
}
```

### **第3步：创建服务配置模板**

在 `nginx/conf/prod/` 目录下创建以下模板文件：

#### **portainer.conf.template**
```nginx
# Portainer 反向代理配置

# 上游服务器定义
upstream portainer {
    server portainer:9000 max_fails=3 fail_timeout=30s;
    keepalive 8;
}

# HTTPS服务器配置
server {
    listen 443 ssl http2;
    server_name ${SUBDOMAIN_PORTAINER}.${DOMAIN_MAIN};
    
    # SSL证书配置
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
    
    # 访问限流
    limit_req zone=portainer burst=20 nodelay;
    
    # 主要代理配置
    location / {
        # IP访问控制（基于环境变量动态生成）
        ${IP_RESTRICTION_BLOCK}
        
        proxy_pass http://portainer;
        
        # 基础代理头部
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时配置
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
        
        # 缓冲配置
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        
        # 禁用代理缓存
        proxy_cache off;
    }
    
    # 健康检查端点
    location /api/system/status {
        proxy_pass http://portainer;
        proxy_set_header Host $host;
        access_log off;
    }
}
```
#### **pgadmin.conf.template**
```nginx
# PgAdmin 反向代理配置

# 上游服务器定义
upstream pgadmin {
    server pgadmin:80 max_fails=3 fail_timeout=30s;
    keepalive 8;
}

# HTTPS服务器配置
server {
    listen 443 ssl http2;
    server_name ${SUBDOMAIN_PGADMIN}.${DOMAIN_MAIN};
    
    # SSL证书配置
    ssl_certificate /etc/nginx/ssl/${DOMAIN_MAIN}.pem;
    ssl_certificate_key /etc/nginx/ssl/${DOMAIN_MAIN}.key;
    
    # SSL安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # 安全头部（数据库管理工具需要更严格的安全设置）
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;" always;
    
    # 访问限流（严格限制）
    limit_req zone=admin burst=10 nodelay;
    
    # 主要代理配置
    location / {
        # IP访问控制（基于环境变量动态生成）
        ${IP_RESTRICTION_BLOCK}
        
        proxy_pass http://pgadmin;
        
        # 基础代理头部
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # PgAdmin特殊头部
        proxy_set_header X-Script-Name "";
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时配置
        proxy_connect_timeout 30s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # 缓冲配置
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        
        # 禁用代理缓存
        proxy_cache off;
    }
    
    # 健康检查端点
    location /misc/ping {
        proxy_pass http://pgadmin;
        proxy_set_header Host $host;
        access_log off;
    }
}
```

#### **redisinsight.conf.template**
```nginx
# RedisInsight 反向代理配置

# 上游服务器定义
upstream redisinsight {
    server redisinsight:5540 max_fails=3 fail_timeout=30s;
    keepalive 8;
}

# HTTPS服务器配置
server {
    listen 443 ssl http2;
    server_name ${SUBDOMAIN_REDIS}.${DOMAIN_MAIN};
    
    # SSL证书配置
    ssl_certificate /etc/nginx/ssl/${DOMAIN_MAIN}.pem;
    ssl_certificate_key /etc/nginx/ssl/${DOMAIN_MAIN}.key;
    
    # SSL安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # 安全头部（数据库管理工具需要更严格的安全设置）
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self' wss:;" always;
    
    # 访问限流（严格限制）
    limit_req zone=admin burst=10 nodelay;
    
    # 主要代理配置
    location / {
        # IP访问控制（基于环境变量动态生成）
        ${IP_RESTRICTION_BLOCK}
        
        proxy_pass http://redisinsight;
        
        # 基础代理头部
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # WebSocket支持（RedisInsight使用WebSocket进行实时更新）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时配置
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
        
        # 缓冲配置
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        
        # 禁用代理缓存
        proxy_cache off;
    }
    
    # 健康检查端点
    location /healthcheck/ {
        proxy_pass http://redisinsight;
        proxy_set_header Host $host;
        access_log off;
    }
}
```

###**第4步：更新docker-compose.prod.yml**

更新nginx服务配置：
```yml
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
    # 使用我们的自定义entrypoint脚本
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

  # ... 其他服务保持不变 ...
```

### **第5步：转换现有配置文件**

将现有的 `nginx/conf/prod/common-locations-prod.conf` 
重命名为 `common-locations-prod.conf.template`（不需要修改内容，因为它不包含动态变量）：

```bash
# 在项目目录中执行
mv nginx/conf/prod/common-locations-prod.conf nginx/conf/prod/common-locations-prod.conf.template
```

### **第6步：配置环境变量**

#### **6.1 创建环境变量模板**

创建 `.env.prod.example` 文件作为配置参考：

```env
# =================================
# 生产环境配置文件示例
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
PGADMIN_PORT=5050
PGADMIN_DEFAULT_EMAIL=admin@yourdomain.com
PGADMIN_DEFAULT_PASSWORD=your_pgadmin_password
PGADMIN_CONFIG_SERVER_MODE=True
PGADMIN_CONFIG_ENHANCED_COOKIE_PROTECTION=True
PGADMIN_CONFIG_WTF_CSRF_ENABLED=True

REDISINSIGHT_PORT=5540
REDISINSIGHT_VERSION=2.70.0
REDISINSIGHT_CONTAINER_NAME=redisinsight_prod

# =================================
# 🔥 Nginx动态配置 - 重要配置项 🔥
# =================================

# === 域名配置 ===
DOMAIN_MAIN=yourdomain.com
SUBDOMAIN_PORTAINER=portainer
SUBDOMAIN_PGADMIN=pgadmin
SUBDOMAIN_REDIS=redis

# === IP访问控制配置 ===
# 设置为 true 启用IP限制，false 禁用
ENABLE_IP_RESTRICTION=true

# 允许访问管理界面的IP地址（填入你的真实公网IP）
# 可以通过 https://ipinfo.io/ip 查看你的公网IP
ALLOWED_IP_HOME=203.0.113.100
ALLOWED_IP_OFFICE=198.51.100.50

# === SSL证书配置（自动基于域名生成路径）===
# 确保证书文件命名为: ${DOMAIN_MAIN}.pem 和 ${DOMAIN_MAIN}.key
# 并放置在 nginx/ssl/ 目录下

# === 前端URL配置 ===
FRONTEND_URL=https://${DOMAIN_MAIN}

# =================================
# 🔐 安全提醒 🔐
# =================================
# 1. 请使用强密码（至少16位字符）
# 2. 定期更换密钥和密码
# 3. 不要将此文件提交到代码仓库
# 4. 建议使用密码管理器生成随机密码
# ================================
```

#### **6.2 更新.gitignore**

确保敏感文件不会被提交：

```bash
# 在 .gitignore 中添加
.env
.env.prod
.env.local
.env.*.local
```

### **第7步：最终目录结构**

完成所有操作后，你的目录结构应该如下：
```
项目根目录/
├── .env.prod.example                      # 环境变量配置模板
├── .env.prod                             # 真实环境变量（不提交到Git）
├── .gitignore                            # 确保包含.env.prod
├── docker-compose.prod.yml               # 更新后的生产compose文件
├── docker-compose.dev.yml                # 开发compose文件，保持不变
├── nginx/
│   ├── entrypoint.sh                     # 🔥 新增：动态配置生成脚本
│   ├── nginx.prod.conf.template          # 🔥 新增：主配置模板
│   ├── nginx.dev.conf                    # 开发环境配置（不变）
│   │
│   ├── conf/
│   │   ├── dev/
│   │   │   └── common-locations-dev.conf # 开发环境location配置
│   │   └── prod/
│   │       ├── portainer.conf.template   # 🔥 新增：Portainer配置模板
│   │       ├── pgadmin.conf.template     # 🔥 新增：PgAdmin配置模板
│   │       ├── redisinsight.conf.template # 🔥 新增：RedisInsight配置模板
│   │       └── common-locations-prod.conf.template # 主应用location配置模板
│   │
│   └── ssl/                              # SSL证书目录
│       ├── yourdomain.com.pem           # 你的SSL证书
│       └── yourdomain.com.key           # 你的SSL私钥
│
├── frontend/                             # 前端代码（不变）
├── backend/                              # 后端代码（不变）
└── ... 其他文件

🚫 删除的文件（已转换为模板）：
   ├── nginx/nginx.prod.conf             # 已重命名为 .template
   └── nginx/conf/prod/*.conf            # 已重命名为 .template
```

## 🚀 **部署指南**

### **部署前准备**

#### **1. 迁移现有配置**

如果你已有运行中的服务，请先备份：

```bash
# 备份现有配置
cp nginx/nginx.prod.conf nginx/nginx.prod.conf.backup
cp -r nginx/conf/prod nginx/conf/prod.backup

# 停止现有服务
docker-compose -f docker-compose.prod.yml down
```

#### **2. 转换配置文件**

```bash
# 重命名现有配置文件为模板
mv nginx/nginx.prod.conf nginx/nginx.prod.conf.template
mv nginx/conf/prod/common-locations-prod.conf nginx/conf/prod/common-locations-prod.conf.template

# 创建启动脚本并设置权限
chmod +x nginx/entrypoint.sh
```

#### **3. 配置环境变量**

```bash
# 复制环境变量模板
cp .env.prod.example .env.prod

# 编辑配置文件，填入你的真实值
nano .env.prod  # 或使用你喜欢的编辑器
```

**重要配置项：**
- `DOMAIN_MAIN`: 你的主域名（如：yourdomain.com）
- `ALLOWED_IP_HOME/ALLOWED_IP_OFFICE`: 你的公网IP地址
- `ENABLE_IP_RESTRICTION`: 设为true启用IP限制，false禁用

#### **4. 准备SSL证书**

确保SSL证书文件名与域名匹配：
```bash
# 证书文件应命名为：
nginx/ssl/yourdomain.com.pem    # 你的域名.pem
nginx/ssl/yourdomain.com.key    # 你的域名.key
```

#### **5. 配置DNS解析**

在你的DNS提供商处添加以下记录：

```dns
A记录：
yourdomain.com        -> 你的服务器IP
portainer.yourdomain.com -> 你的服务器IP  
pgadmin.yourdomain.com   -> 你的服务器IP
redis.yourdomain.com     -> 你的服务器IP
```

### **部署执行**

#### **1. 部署应用**

```bash
# 拉取最新代码
git pull origin master

# 启动生产服务
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 查看启动日志
docker-compose -f docker-compose.prod.yml logs -f nginx
```

#### **2. 验证部署**

```bash
# 检查所有容器状态
docker-compose -f docker-compose.prod.yml ps

# 测试nginx配置
docker exec nginx_proxy_prod nginx -t

# 检查网站访问
curl -I https://yourdomain.com
curl -I https://portainer.yourdomain.com
curl -I https://pgadmin.yourdomain.com
curl -I https://redis.yourdomain.com
```

#### **3. 访问管理界面**

部署成功后，你可以通过以下地址访问：

- 🏠 **主应用**: https://yourdomain.com
- 🐳 **容器管理**: https://portainer.yourdomain.com  
- 🗄️ **数据库管理**: https://pgadmin.yourdomain.com
- 🔄 **Redis监控**: https://redis.yourdomain.com

## ⚡ **优势总结**

### **🔐 安全性**
- ✅ 敏感信息（域名、IP）不暴露在代码中
- ✅ IP白名单访问控制
- ✅ 强制HTTPS和安全头部
- ✅ 速率限制防护

### **🔧 可维护性**
- ✅ 配置模板化，高度通用
- ✅ 开发/生产环境完全隔离  
- ✅ 一键部署，自动配置生成
- ✅ 符合Docker最佳实践

### **🚀 易用性**
- ✅ 任何人都可轻松部署
- ✅ 只需配置环境变量
- ✅ 自动SSL证书路径解析
- ✅ 容器启动时自动验证配置

### **📊 可观测性**
- ✅ 通过Portainer图形化管理容器
- ✅ 通过PgAdmin管理数据库
- ✅ 通过RedisInsight监控缓存
- ✅ 统一的访问日志记录

这个最终版本结合了Gemini方案的简洁性和我的方案的健壮性，是一个生产就绪的解决方案！
