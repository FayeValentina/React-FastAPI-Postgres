# 重构原因
目前我的Web代码已经部署在了OCI的生产环境中正常运行。
在本地的开发环境中，我使用docker desktop轻松管理各个容器。
但是在远程的生产环境，缺乏有效的管理和监控各个容器的手段。
因此我准备添加portainer，来完成容器的管理。

现在有一个问题，我的OCI虚拟机上的应用，只对外暴露了80和443端口。所以即使访问https://<my oci server public ip>:port 也无济于事。为了安全性，我也不想在公网暴露其它的端口。

我从gemini那里了解到，可以通过nginx反向代理+子域名的方式进行配置,实现远程管理虚拟机中的容器。

因为我将这种方式也应用到了现存的两个图形管理工具:pgadmin,redisinsight中。

基于以上需求，经过多次修改后我敲定了如下的重构指南。

这份新指南包含了以下关键改进：

1.  **版本锁定**：为 `redisinsight` 和 `portainer` 锁定了具体的镜像版本，增强了生产环境的稳定性。
2.  **Nginx 目录结构优化**：引入了按环境隔离的 `nginx/conf/prod` 和 `nginx/conf/dev` 目录，使配置更清晰、安全且易于扩展。
3.  **Compose 文件更新**：明确了 `docker-compose.prod.yml` 中 Nginx 服务的 `volumes` 挂载需要指向新的配置目录。
4.  **注释和说明**：在配置文件中加入了少量注释，以解释关键决策。

-----

### **最终重构指南 (V2 - 整合版)**

这是根据我们深入讨论后，整合了所有最佳实践的最终实施方案。

#### **第 1 步：重构 Nginx 配置目录结构 (重要)**

为了实现开发与生产环境的配置完全隔离，我们首先需要优化目录结构。

1.  **创建新目录**：在项目根目录下的 `nginx` 文件夹中，创建一个名为 `conf` 的新目录。
2.  在 `nginx/conf` 内部，再创建两个子目录：`dev` 和 `prod`。
3.  **迁移配置文件**：
      * 将现有的 `nginx/conf.d/common-locations-prod.conf` 文件移动到 `nginx/conf/prod/` 目录中。
      * 将现有的 `nginx/conf.d/common-locations-dev.conf` 文件移动到 `nginx/conf/dev/` 目录中。
4.  旧的 `nginx/conf.d` 目录现在可以安全删除了。

**最终目录结构应如下所示：**

```
nginx/
├── conf/
│   ├── dev/
│   │   └── common-locations-dev.conf
│   └── prod/
│       ├── common-locations-prod.conf
│       ├── portainer.conf
│       ├── pgadmin.conf
│       └── redisinsight.conf
├── ssl/
├── nginx.dev.conf
└── nginx.prod.conf
```

-----

#### **第 2 步：更新 `docker-compose.prod.yml`**

##### **2.1 - 更新 Nginx 服务的 Volume 挂载**

请在 `docker-compose.prod.yml` 文件中找到 `nginx` 服务，并修改其 `volumes` 部分，以指向我们新创建的 `prod` 配置目录。
同时在depends_on的依赖关系部分，新增三个管理容器。
```yaml
# ... services ...

  nginx:
    image: nginx:alpine
    container_name: nginx_proxy_prod
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.prod.conf:/etc/nginx/nginx.conf:ro
      # [修正] 只挂载生产环境的配置目录
      - ./nginx/conf/prod:/etc/nginx/conf.d:ro  
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - frontend_build:/usr/share/nginx/html:ro
      - prod_nginx_logs:/var/log/nginx
    # ... 中间配置保持不变 ...
    depends_on:
      - frontend_builder
      - backend
      - portainer     # 新增
      - pgadmin       # 新增  
      - redisinsight  # 新增
    # ... 其余配置保持不变 ...
```

同时 `docker-compose.dev.yml` 文件中 `nginx`的挂载目录 `volumes` 也需要修正。
```yaml
# ... services ...
  # nginx 反向代理服务
  nginx:
    image: nginx:alpine
    container_name: nginx_proxy
    ports:
      - "80:80"
      - "443:443"  # 为将来的 SSL 配置预留
    volumes:
      - ./nginx/nginx.dev.conf:/etc/nginx/nginx.conf:ro
      # - ./nginx/conf.d:/etc/nginx/conf.d:ro 这里需要修正，改为:
      - ./nginx/conf/dev:/etc/nginx/conf.d:ro 
      - dev_nginx_logs:/var/log/nginx
    depends_on:
      - frontend
      - backend
```
##### **2.2 - 更新/新增管理工具服务**

现在，请在同一个 `docker-compose.prod.yml` 文件中，更新 `pgadmin`、`redisinsight` 并新增 `portainer` 服务。

```yaml
# ... services ...

  pgadmin:
    # [版本锁定] 建议使用一个具体的版本号而非:latest或大版本
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

  redisinsight:
    # [修正] 版本已锁定，配置更稳定
    image: redislabs/redisinsight:2.70.0
    container_name: redisinsight_prod
    env_file:
      - .env.prod
    expose:
      - "5540"
    volumes:
      - prod_redisinsight_data:/db
    environment:
      - RITRUSTEDORIGINS=https://redis.warabi.dpdns.org
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

  # 新增容器
  portainer:
    # [修正] 版本已锁定
    image: portainer/portainer-ce:2.27.9-alpine
    container_name: portainer_prod
    expose:
      - "9000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock #如果需要完整的管理功能，需要移除 :ro 标记。
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

# ... volumes ...
# 请确保为新增的服务添加 volume
volumes:
  # ...
  prod_redisinsight_data:
    driver: local
  prod_portainer_data:    # 新增
    driver: local
  # ...
```

-----

#### **第 3 步：创建新的 Nginx 配置文件**

在**新的 `nginx/conf/prod/` 目录**下，创建以下三个文件。

##### **`nginx/conf/prod/portainer.conf` (新建)**

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
    server_name portainer.warabi.dpdns.org;  # 修改为你的子域名
    
    # SSL证书配置
    ssl_certificate /etc/nginx/ssl/warabi.dpdns.org.pem;
    ssl_certificate_key /etc/nginx/ssl/warabi.dpdns.org.key;
    
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
    
    # 访问限流（可选，如果nginx.prod.conf中已定义limit_req_zone）
    limit_req zone=portainer burst=20 nodelay;
    
    # 主要代理配置
    location / {
        proxy_pass http://portainer;
        
        # 基础代理头部
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # WebSocket支持（通用配置，支持所有WebSocket连接）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时配置
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;  # Portainer操作可能需要较长时间
        
        # 缓冲配置
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        
        # 禁用代理缓存（确保实时性）
        proxy_cache off;
    }
    
    # 健康检查端点（不记录日志）
    location /api/system/status {
        proxy_pass http://portainer;
        proxy_set_header Host $host;
        access_log off;
    }
    
    # 可选：IP访问限制（取消注释以启用）
    # allow YOUR_HOME_IP;
    # allow YOUR_OFFICE_IP; 
    # deny all;
}
```

##### **`nginx/conf/prod/pgadmin.conf` (新建)**

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
    server_name pgadmin.warabi.dpdns.org;
    
    # SSL证书配置
    ssl_certificate /etc/nginx/ssl/warabi.dpdns.org.pem;
    ssl_certificate_key /etc/nginx/ssl/warabi.dpdns.org.key;
    
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
        proxy_pass http://pgadmin;
        
        # 基础代理头部
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # PgAdmin可能需要的特殊头部
        proxy_set_header X-Script-Name "";
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时配置（数据库操作可能需要较长时间）
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
    
    # 可选：严格的IP访问控制（数据库管理工具建议启用）
    # allow YOUR_HOME_IP;
    # allow YOUR_OFFICE_IP;
    # deny all;
}
```

##### **`nginx/conf/prod/redisinsight.conf` (新建)**

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
    server_name redis.warabi.dpdns.org;
    
    # SSL证书配置
    ssl_certificate /etc/nginx/ssl/warabi.dpdns.org.pem;
    ssl_certificate_key /etc/nginx/ssl/warabi.dpdns.org.key;
    
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
        proxy_read_timeout 300s;  # Redis命令可能需要较长时间
        
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
    
    # 可选：严格的IP访问控制（数据库管理工具建议启用）
    # allow YOUR_HOME_IP;
    # allow YOUR_OFFICE_IP;
    # deny all;
}
```

-----

#### **第 4 步：更新主 Nginx 配置文件 `nginx.prod.conf`**

最后，请用以下内容替换现有的 `nginx/nginx.prod.conf` 文件。这个版本保持了您原有的健壮配置，并对 `include` 指令的逻辑进行了说明。

```nginx
user nginx;
worker_processes auto;
# ... (events 块等全局配置保持不变) ...

http {
    # ... (log_format, sendfile 等全局配置保持不变) ...

    # 速率限制
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
    # 新增
    limit_req_zone $binary_remote_addr zone=admin:10m rate=2r/m;
    limit_req_zone $binary_remote_addr zone=portainer:10m rate=5r/m;
    # ...

    upstream backend {
        server backend:8000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    # HTTP -> HTTPS 统一重定向 (已包含所有域名)
    server {
        listen 80;
        server_name warabi.dpdns.org
                    portainer.warabi.dpdns.org
                    pgadmin.warabi.dpdns.org
                    redis.warabi.dpdns.org;
        return 301 https://$server_name$request_uri;
    }

    # 主应用 HTTPS 服务器配置
    # 注意：这个 server 块和其他管理工具的 server 块是并列的。
    server {
        listen 443 ssl http2;
        server_name warabi.dpdns.org;
        
        ssl_certificate /etc/nginx/ssl/warabi.dpdns.org.pem;
        ssl_certificate_key /etc/nginx/ssl/warabi.dpdns.org.key;
        
        # [说明] 此处 include 的文件只包含 location 块，
        # 因此它必须在 server 块内部。
        include /etc/nginx/conf.d/common-locations-prod.conf;
    }

    # [说明] 此处 include 的文件 (pgadmin.conf等) 包含完整的 server 块，
    # 因此它们必须在 http 块内部、任何 server 块外部。
    # Nginx 会将它们作为独立的、并列的 HTTPS 服务来加载。
    include /etc/nginx/conf.d/pgadmin.conf;
    include /etc/nginx/conf.d/portainer.conf;
    include /etc/nginx/conf.d/redisinsight.conf;
}
```

-----

这套重构方案结合了我们所有的讨论成果，将使您的项目配置更加清晰、安全和易于维护。
