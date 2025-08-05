# 🚀 部署指南

## 快速部署

### 前置要求

确保服务器已安装：
- Docker
- Docker Compose
- Git

如果未安装，请先运行 Docker 安装脚本：
```bash
./install-docker.sh
```

### 方法一：使用自动部署脚本（推荐）

```bash
# 一键部署到指定服务器（自动检测 private IP）
./deploy.sh <public-ip>

# 例如：
./deploy.sh 8.213.226.34

# 或者指定 private IP：
./deploy.sh 8.213.226.34 172.16.0.10
```

### 方法二：手动配置

1. **复制环境变量模板**
```bash
cp .env.template .env
```

2. **编辑配置文件**
```bash
nano .env
```

3. **修改关键配置**
```env
# 服务器 IP 地址
PUBLIC_IP=your-public-ip
PRIVATE_IP=your-private-ip

# 前端访问地址
FRONTEND_URL=http://your-public-ip:3000

# 后端 API 地址
API_URL=http://your-public-ip:8001

# OpenAI API 密钥（用于 AI 功能）
OPENAI_API_KEY=your-openai-api-key
```

4. **启动服务**
```bash
# 拉取最新代码
git pull origin main

# 重新构建并启动
docker-compose up -d --build
```

## 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `PUBLIC_IP` | 服务器公网 IP（用户访问） | - |
| `PRIVATE_IP` | 服务器内网 IP（内部服务通信） | 同 `PUBLIC_IP` |
| `FRONTEND_URL` | 前端访问地址 | `http://localhost:3000` |
| `API_URL` | 后端 API 地址 | `http://localhost:8001` |
| `DATABASE_URL` | 数据库连接字符串 | `mysql+aiomysql://...` |
| `REDIS_URL` | Redis 连接字符串 | `redis://redis:6379` |
| `MINIO_ENDPOINT` | MinIO 服务地址 | `minio:9000` |
| `OPENAI_API_KEY` | OpenAI API 密钥 | - |
| `DEBUG` | 调试模式 | `true` |

## 验证部署

1. **检查服务状态**
```bash
docker-compose ps
```

2. **查看日志**
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

3. **访问测试**
   - 前端: `http://your-server-ip:3000`
   - 后端: `http://your-server-ip:8001`
   - API 文档: `http://your-server-ip:8001/docs`

## 迁移到新主机

1. **在新主机上克隆项目**
```bash
git clone https://github.com/your-username/youtube-slicer.git
cd youtube-slicer
```

2. **运行部署脚本**
```bash
# 自动检测 private IP
./deploy.sh <new-public-ip>

# 或者指定 private IP
./deploy.sh <new-public-ip> <new-private-ip>
```

3. **验证所有服务正常运行**
```bash
docker-compose ps
```

## 网络架构说明

### Public IP vs Private IP

- **Public IP**: 用于用户访问前端和 API
- **Private IP**: 用于内部服务通信（数据库、Redis、MinIO）

### 服务通信架构

```
用户访问 (Public IP)
    ↓
前端 (3000端口) ←→ 后端 API (8001端口)
    ↓                    ↓
[Public IP]          [Private IP 内部通信]
                        ↓
                    MySQL (3306端口)
                    Redis (6379端口)  
                    MinIO (9000端口)
```

## Docker 安装指南

### 自动安装（推荐）

```bash
# 运行 Docker 安装脚本
./install-docker.sh

# 安装完成后重新登录或运行
newgrp docker
```

### 手动安装

#### CentOS/RHEL
```bash
# 更新包管理器
sudo yum update -y

# 安装 Docker
sudo yum install -y docker

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 添加用户到 docker 组
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 重新登录或运行
newgrp docker
```

#### Ubuntu/Debian
```bash
# 更新包管理器
sudo apt update
sudo apt install -y docker.io docker-compose

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 添加用户到 docker 组
sudo usermod -aG docker $USER

# 重新登录或运行
newgrp docker
```

## 故障排除

### 常见问题

1. **Docker 未安装或未运行**
   ```bash
   # 检查 Docker 状态
   docker --version
   docker info
   
   # 如果未安装，运行安装脚本
   ./install-docker.sh
   ```

2. **权限错误**
   ```bash
   # 添加用户到 docker 组
   sudo usermod -aG docker $USER
   
   # 重新登录或运行
   newgrp docker
   ```

3. **CORS 错误**
   - 检查 `.env` 文件中的 `FRONTEND_URL` 是否正确
   - 确保后端服务已重启

4. **数据库连接失败**
   - 等待 MySQL 容器完全启动
   - 检查数据库连接字符串

5. **前端构建失败**
   - 确保所有依赖已安装
   - 检查 Node.js 版本兼容性

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f mysql
docker-compose logs -f redis
```

### 重启服务

```bash
# 重启特定服务
docker-compose restart backend

# 重启所有服务
docker-compose restart
```

## 生产环境建议

1. **安全性**
   - 更改默认密码和密钥
   - 使用 HTTPS（配置 Nginx 反向代理）
   - 关闭调试模式 `DEBUG=false`

2. **性能优化**
   - 配置 SSL 终止
   - 使用 CDN 加速静态资源
   - 监控资源使用情况

3. **备份策略**
   - 定期备份数据库
   - 备份重要配置文件
   - 备份上传的文件