#!/bin/bash

echo "启动应用服务..."

# 检查 nginx 配置
if [ ! -f nginx/nginx.conf ]; then
    echo "错误: nginx/nginx.conf 不存在"
    exit 1
fi

# 启动服务
echo "启动 Docker Compose 服务..."
docker-compose up -d

echo "等待服务启动..."
sleep 10

# 检查服务状态
echo "检查服务状态..."
docker-compose ps

echo "应用已启动！"
echo "访问地址: http://localhost"
echo "API 文档: http://localhost/api/docs"
echo "PgAdmin: http://localhost:${PGADMIN_PORT:-5050}"
echo "RabbitMQ 管理: http://localhost:15672"
echo "Redis Insight: http://localhost:${REDISINSIGHT_PORT:-8001}"