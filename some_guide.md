好的，我们来整合所有这些优秀的建议，并为你评估两种环境变量处理方式的优劣。

### 评估：`docker context` vs 在命令前 `export` 环境变量

这是一个很好的问题，涉及到便利性、安全性和现代 Docker 实践的权衡。

1.  **在 `docker compose` 命令前 `export` 环境变量**

      * **工作方式**：在 `ssh-action` 的脚本内部，通过 `export $(echo "${{ secrets.ENV_PROD_VARS }}" | xargs)` 命令，将密钥（secrets）动态加载到当前的 SSH 会话中。这些环境变量只在当前脚本执行期间有效。
      * **优点**：
          * **易于实施**：你几乎不需要改变现有的工作流，只需修改 `ssh-action` 中的几行脚本即可。
          * **显著提升安全性**：相比于在服务器上创建一个 `.env.prod` 文件，这种方式避免了将密钥明文存储在磁盘上，是一个巨大的进步。
      * **缺点**：
          * 环境变量在执行期间存在于服务器的进程环境中，理论上如果服务器被攻破，攻击者有可能在脚本运行时读取到它们。但这种风险远小于文件泄露。

2.  **使用 `docker context` 连接远程 Docker 主机**

      * **工作方式**：这是一种更现代、更“Docker 原生”的方式。你可以在 GitHub Actions 的 runner 上创建一个 Docker “上下文（context）”，让它安全地指向你 Oracle Cloud 服务器上的 Docker 守护进程。这样，你在 GitHub Actions 中运行的 `docker` 命令就像在本地执行一样，但实际上是在远程服务器上操作。
      * **优点**：
          * **最佳安全性**：通信是加密的，并且你不需要在 `deploy` 阶段使用通用的 SSH 连接来执行 Docker 命令。环境变量可以直接在 GitHub Actions 的工作流中注入，完全不接触远程服务器的 shell 环境。
          * **更简洁的工作流**：部署脚本会变得更清晰，因为它移除了大部分 `ssh-action` 的复杂脚本，代之以标准的 `docker` 或 `docker compose` 命令。
      * **缺点**：
          * **初始设置更复杂**：你需要在远程服务器上配置 Docker daemon 以允许安全远程连接，并在 GitHub Actions 中使用密钥（如 SSH 证书）来设置 `docker context`。这需要一些额外的学习和配置成本。

#### **评估结论**

对于你目前的场景：

  * **推荐方案**：**在 `ssh-action` 中使用 `export` 命令。**
  * **理由**：这个方案为你带来了立竿见影的安全提升，并且实施起来非常简单，几乎没有额外学习成本。它完美地平衡了安全性、复杂性和效果。

`docker context` 是一个更高级、更专业的方案，非常值得你在未来项目做大、对安全性要求更高时去研究和采纳。但就目前而言，我们先用最直接有效的方式完成整合。

-----

### 整合后的 `deploy.yml` 文件

这是结合了所有最佳实践的最终版本。我已经将 CI 步骤拆分为并行任务，并加入了所有讨论过的改进点。

**请注意：** 在 `Health check` 部分，我使用了一个示例的健康检查接口 `http://localhost/api/v1/health/check`。**你需要将它替换成你后端真实存在的、能反映服务是否就绪的 API 接口**。

```yaml
name: Deploy to Oracle Cloud

on:
  push:
    branches: [ master ]
  pull_request:
    branches: [ master ]

# 1. 防止并发部署，确保同分支只有一个部署任务运行
concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: true

# 2. 限制 GITHUB_TOKEN 的权限为只读，遵循最小权限原则
permissions:
  contents: read

env:
  # 从 GitHub 仓库变量中获取域名信息
  DOMAIN_MAIN: ${{ vars.DOMAIN_MAIN }}
  FRONTEND_URL: https://${{ vars.DOMAIN_MAIN }}

jobs:
  # ====================================================================
  # CI Job 1 (并行): 前端代码质量检查、测试和构建
  # ====================================================================
  ci-frontend:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json
    
    - name: Install frontend dependencies
      working-directory: ./frontend
      run: npm ci
    
    - name: Run frontend linting
      working-directory: ./frontend
      run: npm run lint
    
    # 3. 增加前端测试步骤
    - name: Run frontend tests
      working-directory: ./frontend
      # 假设 'npm test' 脚本已配置好，'-- --ci' 是为了在非交互式环境中运行
      run: npm test -- --watch=false

    - name: Build frontend
      working-directory: ./frontend
      run: npm run build

  # ====================================================================
  # CI Job 2 (并行): 后端代码质量检查与测试
  # ====================================================================
  ci-backend:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install Poetry
      uses: snok/install-poetry@v1
    
    - name: Load cached venv
      id: cached-poetry-dependencies
      uses: actions/cache@v3
      with:
        path: backend/.venv
        key: venv-${{ runner.os }}-${{ hashFiles('**/poetry.lock') }}
    
    - name: Install backend dependencies
      if: steps.cached-poetry-dependencies.outputs.cache-hit != 'true'
      working-directory: ./backend
      run: poetry install --no-interaction --no-root
      
    # 4. 增加后端 Lint 步骤
    - name: Run backend lint
      working-directory: ./backend
      run: poetry run ruff check .

    # 5. 增加后端测试步骤
    - name: Run backend tests
      working-directory: ./backend
      run: poetry run pytest

  # ====================================================================
  # CI Job 3: 测试 Docker 镜像能否成功构建
  # ====================================================================
  test-docker-build:
    # 依赖前后端 CI 任务成功
    needs: [ci-frontend, ci-backend]
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    # 6. 设置 Buildx 并缓存 Docker 镜像层，加速构建
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Cache Docker layers
      uses: actions/cache@v3
      with:
        path: /tmp/.buildx-cache
        key: ${{ runner.os }}-buildx-${{ github.sha }}
        restore-keys: |
          ${{ runner.os }}-buildx-

    - name: Test Docker builds
      run: |
        docker compose -f docker-compose.prod.yml build

  # ====================================================================
  # CD Job: 部署到 Oracle Cloud
  # ====================================================================
  deploy:
    # 依赖所有 CI 任务成功
    needs: test-docker-build
    runs-on: ubuntu-latest
    # 仅在 master 分支 push 事件时触发
    if: github.ref == 'refs/heads/master' && github.event_name == 'push'
    environment:
      name: production
      url: ${{ env.FRONTEND_URL }}
    
    steps:
    - name: Deploy to Oracle Cloud
      uses: appleboy/ssh-action@v1.0.0
      with:
        host: ${{ secrets.OCI_SSH_HOST }}
        username: ${{ secrets.OCI_SSH_USER }}
        key: ${{ secrets.OCI_SSH_KEY }}
        script: |
          set -euo pipefail

          cd ~/web-app
          
          echo "🔄 Pulling latest code..."
          git pull origin master
          
          # 7. 不再创建 .env.prod 文件，直接将 secrets 导出为环境变量
          echo "🔒 Exporting production environment variables..."
          export $(echo "${{ secrets.ENV_PROD_VARS }}" | xargs)

          echo "🔧 Ensuring nginx entrypoint permissions..."
          chmod +x nginx/entrypoint.sh || true
          sed -i 's/\r$//' nginx/entrypoint.sh || true
                    
          echo "🏗️ Building production images..."
          docker compose -f docker-compose.prod.yml build
          
          echo "🛑 Stopping existing services..."
          docker compose -f docker-compose.prod.yml down
          
          echo "🚀 Starting new services..."
          docker compose -f docker-compose.prod.yml up -d --pull always

          # 8. 使用健康检查代替固定等待，提升部署可靠性
          echo "⏳ Waiting for services to be ready..."
          timeout 120s bash -c ' \
            until curl -s -f http://localhost/api/v1/health/check; do \
              echo "Service not ready yet, retrying in 5 seconds..."; \
              sleep 5; \
            done'
          
          echo "✅ Checking service status..."
          docker compose -f docker-compose.prod.yml ps
          
          echo "🧹 Cleaning up unused Docker resources..."
          docker system prune -af
          
          echo "🎉 Deployment completed successfully!"

```