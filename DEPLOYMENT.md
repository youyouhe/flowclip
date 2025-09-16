# Flowclip 部署指南

## 🚀 快速开始

### 1. 自动部署（推荐）

使用部署脚本自动完成所有配置：

```bash
# 单 IP 环境（自动检测内网 IP）
./deploy.sh 8.213.226.34

# 或者指定内网 IP
./deploy.sh 8.213.226.34 172.16.0.10
```

### 2. 验证部署

运行配置验证脚本检查部署状态：

```bash
./verify-config.sh
```

## 📋 系统要求

### 必需软件
- **Docker**: >= 20.10
- **Docker Compose**: >= 1.29
- **Git**: 用于代码拉取

### 推荐配置
- **CPU**: 2核心以上
- **内存**: 4GB以上
- **存储**: 20GB以上可用空间
- **网络**: 稳定的互联网连接

## 🔧 部署脚本详解

### deploy.sh 功能

1. **环境检测**
   - 自动检测内网 IP
   - 验证 Docker 环境
   - 检查必要工具

2. **配置生成**
   - 创建 `.env` 文件
   - 更新 `docker-compose.yml`
   - 配置双端点 MinIO

3. **服务部署**
   - 拉取最新代码
   - 构建容器镜像
   - 启动所有服务

4. **部署验证**
   - 显示访问地址
   - 提供管理命令
   - 输出系统状态

### 生成的配置

#### .env 文件
```bash
# 服务器配置
PUBLIC_IP=8.213.226.34
PRIVATE_IP=172.16.0.10

# Docker 内部通信
FRONTEND_URL=http://frontend:3000
API_URL=http://backend:8001

# 数据库配置
DATABASE_URL=mysql+aiomysql://youtube_user:youtube_password@mysql:3306/youtube_slicer?charset=utf8mb4

# MinIO 双端点配置
MINIO_ENDPOINT=minio:9000
MINIO_PUBLIC_ENDPOINT=http://8.213.226.34:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=youtube-videos
```

#### docker-compose.yml 特性
- **服务发现**: 使用容器名称进行内部通信
- **网络隔离**: 独立的 Docker 网络
- **数据持久化**: 自动管理数据卷
- **健康检查**: 自动服务监控

## 🌐 访问地址

### 外部访问（用户）
- **前端**: http://[PUBLIC_IP]:3000
- **API**: http://[PUBLIC_IP]:8001
- **API 文档**: http://[PUBLIC_IP]:8001/docs
- **MinIO 控制台**: http://[PUBLIC_IP]:9001

### 内部通信（Docker）
- **Frontend**: http://frontend:3000
- **Backend**: http://backend:8001
- **MinIO**: http://minio:9000
- **MySQL**: mysql:3306
- **Redis**: redis:6379

## 📊 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Browser   │───▶│   Frontend      │────│   Backend       │
│   (外部访问)      │    │   (React)       │    │   (FastAPI)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       ▼
         │              ┌─────────────────┐    ┌─────────────────┐
         │              │   MinIO Public  │    │   MinIO Internal│
         └─────────────▶│   (文件下载)     │◀───│   (存储管理)     │
                        └─────────────────┘    └─────────────────┘
```

## 🔧 管理命令

### 查看状态
```bash
docker-compose ps                    # 服务状态
docker-compose logs -f               # 实时日志
docker-compose logs backend          # 后端日志
docker-compose logs frontend         # 前端日志
```

### 服务管理
```bash
docker-compose up -d --build        # 重新构建并启动
docker-compose restart               # 重启所有服务
docker-compose down                  # 停止所有服务
docker-compose down -v               # 停止并删除数据
```

### 数据管理
```bash
# 查看 MySQL
docker exec -it youtube-slicer-mysql mysql -u youtube_user -pyoutube_password youtube_slicer

# 查看 Redis
docker exec -it youtube-slicer-redis redis-cli

# 查看 MinIO
docker exec -it youtube-slicer-minio mc ls local/youtube-videos
```

## 🐛 故障排除

### 常见问题

1. **CORS 错误**
   - 检查 `.env` 中的 IP 配置
   - 重新运行部署脚本
   - 清除浏览器缓存

2. **WebSocket 连接失败**
   - 确认后端服务正常运行
   - 检查防火墙设置
   - 验证网络连接

3. **MinIO 下载失败**
   - 检查 `MINIO_PUBLIC_ENDPOINT` 配置
   - 确认端口 9000 已开放
   - 验证 MinIO 服务状态

4. **数据库连接错误**
   - 等待 MySQL 完全启动
   - 检查数据库配置
   - 查看容器日志

### 日志分析
```bash
# 查看特定服务错误
docker-compose logs backend | grep ERROR
docker-compose logs celery | grep ERROR

# 查看最近日志
docker-compose logs --tail=50 backend
```

### 性能优化
```bash
# 扩展 Celery 工作进程
docker-compose up -d --scale celery-worker=3

# 清理未使用的资源
docker system prune -f
```

## 🔄 更新流程

### 代码更新
```bash
git pull origin main
./deploy.sh <public-ip>
```

### 配置更新
```bash
# 修改 .env 文件后重启
docker-compose restart
```

### 版本回滚
```bash
git checkout <tag>
./deploy.sh <public-ip>
```

## 📞 技术支持

如果遇到问题，请按以下步骤排查：

1. **运行验证脚本**：`./verify-config.sh`
2. **检查服务日志**：`docker-compose logs -f`
3. **查看本文档**：故障排除部分
4. **提交 Issue**：在 GitHub 仓库中创建问题

## 📝 开发环境

如需本地开发，请参考开发文档：
- [开发指南](./DEVELOPMENT.md)
- [API 文档](./backend/docs/)
- [前端开发](./frontend/README.md)