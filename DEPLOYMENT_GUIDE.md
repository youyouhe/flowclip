# Flowclip 非Docker部署指南

本指南将帮助您在不使用Docker的情况下部署Flowclip视频处理系统。

## 系统架构

Flowclip系统由以下组件组成：

### 核心存储组件
- **MySQL 8.0**: 主数据库，存储用户、项目、视频元数据
- **Redis**: 缓存和任务队列，支持Celery异步处理
- **MinIO**: 对象存储服务，存储视频文件和媒体资源

### 应用服务组件
- **Backend API**: FastAPI应用，提供REST API服务 (端口: 8001)
- **TUS回调服务器**: 处理大文件上传回调 (端口: 9090)
- **MCP服务器**: Model Context Protocol服务器 (端口: 8002)
- **Frontend**: React前端应用 (端口: 3000)
- **Celery Worker**: 异步任务处理器
- **Celery Beat**: 定时任务调度器

## 部署步骤

### 第一步：系统要求

#### 操作系统支持
- Ubuntu 18.04+ / Debian 9+
- CentOS 7+ / RHEL 7+

#### 硬件要求
- CPU: 4核心以上
- 内存: 8GB以上 (推荐16GB)
- 存储: 100GB以上可用空间
- 网络: 稳定的互联网连接

### 第二步：Root权限安装

运行系统级组件安装脚本：

```bash
# 下载安装脚本
curl -O https://your-domain.com/install_root.sh

# 运行安装脚本
sudo bash install_root.sh
```

该脚本将自动安装和配置：

1. **系统更新和基础工具**
   - 系统包更新
   - 基础开发工具 (git, curl, wget, build-essential等)

2. **Python 3.11环境**
   - 安装Python 3.11
   - 配置pip和虚拟环境支持

3. **核心存储组件**
   - MySQL 8.0 (端口: 3306)
   - Redis (端口: 6379)
   - MinIO (API: 9000, Console: 9001)

4. **Node.js环境**
   - Node.js 18.x
   - PM2进程管理器

5. **媒体处理库**
   - FFmpeg
   - 图像处理库 (libsm6, libxext6等)

6. **专用用户和目录**
   - 创建flowclip用户
   - 设置项目目录和环境配置

### 第三步：用户级配置

切换到专用用户并配置应用环境：

```bash
# 切换到flowclip用户
sudo su - flowclip

# 进入项目目录
cd EchoClip

# 运行用户配置脚本
bash install_user.sh
```

该脚本将：

1. **检查系统依赖**
   - 验证Python、Node.js、Redis、MySQL连接

2. **配置Python环境**
   - 创建虚拟环境
   - 安装后端Python依赖

3. **配置数据库**
   - 运行数据库迁移
   - 创建测试用户

4. **配置前端环境**
   - 安装Node.js依赖

5. **创建服务管理脚本**
   - PM2配置文件
   - 服务启动/停止/重启脚本

### 第四步：启动服务

#### 方式一：使用PM2管理所有服务

```bash
# 启动所有服务
./start_services.sh

# 查看服务状态
pm2 status

# 查看日志
pm2 logs

# 停止所有服务
./stop_services.sh

# 重启所有服务
./restart_services.sh
```

#### 方式二：手动启动各个服务

```bash
# 1. 启动后端服务
cd backend
python start_services.py

# 2. 在新终端启动Celery Worker
cd backend
python start_celery.py worker --loglevel=info --concurrency=4

# 3. 在新终端启动Celery Beat
cd backend
python start_celery.py beat --loglevel=info

# 4. 在新终端启动前端服务
cd frontend
npm run dev
```

## 访问地址

部署完成后，可通过以下地址访问各服务：

- **前端应用**: http://localhost:3000
- **后端API**: http://localhost:8001
- **API文档**: http://localhost:8001/docs
- **MinIO控制台**: http://localhost:9001
- **MinIO API**: http://localhost:9000

## 配置说明

### 环境变量配置

主要配置文件位于项目根目录的`.env`文件：

```bash
# 数据库配置
DATABASE_URL=mysql+aiomysql://youtube_user:youtube_password@localhost:3306/youtube_slicer?charset=utf8mb4

# Redis配置
REDIS_URL=redis://localhost:6379

# MinIO配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=i4W5jAG1j9w2MheEQ7GmYEotBrkAaIPSmLRQa6Iruc0=
MINIO_SECRET_KEY=TcFA+qUwvCnikxANs7k/HX7oZz2zEjLo3RakL1kZt5k=
MINIO_BUCKET_NAME=youtube-videos

# 应用配置
SECRET_KEY=your-secret-key-change-in-production
FRONTEND_URL=http://localhost:3000
BACKEND_PUBLIC_URL=http://127.0.0.1:8001

# TUS配置 (大文件上传)
TUS_API_URL=http://localhost:8000
TUS_UPLOAD_URL=http://localhost:1080
TUS_CALLBACK_PORT=9090
TUS_FILE_SIZE_THRESHOLD_MB=10
```

### MinIO配置

MinIO的访问信息：
- **API端点**: http://localhost:9000
- **控制台端点**: http://localhost:9001
- **访问密钥**: `i4W5jAG1j9w2MheEQ7GmYEotBrkAaIPSmLRQa6Iruc0=`
- **秘密密钥**: `TcFA+qUwvCnikxANs7k/HX7oZz2zEjLo3RakL1kZt5k=`

### MySQL配置

MySQL数据库信息：
- **端口**: 3306
- **数据库**: youtube_slicer
- **用户**: youtube_user
- **密码**: youtube_password

## 服务管理

### PM2命令

```bash
# 查看所有服务状态
pm2 status

# 查看特定服务日志
pm2 logs flowclip-backend

# 重启特定服务
pm2 restart flowclip-backend

# 停止特定服务
pm2 stop flowclip-backend

# 删除服务
pm2 delete flowclip-backend

# 保存PM2配置
pm2 save

# 设置开机自启
pm2 startup
```

### 系统服务管理

```bash
# MySQL服务
sudo systemctl status mysql
sudo systemctl restart mysql
sudo systemctl stop mysql

# Redis服务
sudo systemctl status redis
sudo systemctl restart redis
sudo systemctl stop redis

# MinIO服务
sudo systemctl status minio
sudo systemctl restart minio
sudo systemctl stop minio
```

## 故障排除

### 常见问题

#### 1. MySQL连接失败
```bash
# 检查MySQL服务状态
sudo systemctl status mysql

# 检查MySQL日志
sudo tail -f /var/log/mysql/error.log

# 测试连接
mysql -uyoutube_user -pyoutube_password -h localhost
```

#### 2. Redis连接失败
```bash
# 检查Redis服务状态
sudo systemctl status redis

# 测试连接
redis-cli ping

# 检查Redis配置
sudo cat /etc/redis/redis.conf | grep -v "^#"
```

#### 3. MinIO无法访问
```bash
# 检查MinIO服务状态
sudo systemctl status minio

# 查看MinIO日志
sudo journalctl -u minio -f

# 检查防火墙设置
sudo ufw status
sudo ufw allow 9000
sudo ufw allow 9001
```

#### 4. 前端无法访问后端
检查后端服务是否正常运行：
```bash
# 检查后端进程
ps aux | grep uvicorn

# 测试API端点
curl http://localhost:8001/health

# 检查防火墙设置
sudo ufw allow 8001
```

### 日志位置

- **PM2日志**: `~/EchoClip/logs/`
- **MySQL日志**: `/var/log/mysql/`
- **Redis日志**: `/var/log/redis/`
- **MinIO日志**: `journalctl -u minio`
- **系统日志**: `/var/log/syslog`

## 性能优化

### MySQL优化
```sql
-- 优化MySQL配置
SET GLOBAL innodb_buffer_pool_size = 2147483648; -- 2GB
SET GLOBAL max_connections = 200;
SET GLOBAL query_cache_size = 67108864; -- 64MB
```

### Redis优化
```bash
# 编辑Redis配置
sudo nano /etc/redis/redis.conf

# 优化参数
maxmemory 2gb
maxmemory-policy allkeys-lru
```

### 系统优化
```bash
# 增加文件描述符限制
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# 优化内核参数
echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

## 安全建议

1. **更改默认密码**
   - 修改MySQL用户密码
   - 修改MinIO访问密钥
   - 设置强密码的应用SECRET_KEY

2. **配置防火墙**
   ```bash
   sudo ufw enable
   sudo ufw allow ssh
   sudo ufw allow 3000  # 前端
   sudo ufw allow 8001  # 后端API
   sudo ufw deny 3306   # 拒绝外部访问MySQL
   sudo ufw deny 6379   # 拒绝外部访问Redis
   ```

3. **SSL证书**
   - 为生产环境配置HTTPS
   - 使用Let's Encrypt免费证书

4. **定期备份**
   - MySQL数据库备份
   - MinIO存储备份
   - 配置文件备份

## 监控和维护

### 健康检查脚本

创建健康检查脚本 `health_check.sh`：

```bash
#!/bin/bash

# 检查各服务状态
echo "=== Flowclip 健康检查 ==="

# MySQL
if mysql -uyoutube_user -pyoutube_password -e "SELECT 1;" &>/dev/null; then
    echo "✓ MySQL: 正常"
else
    echo "✗ MySQL: 异常"
fi

# Redis
if redis-cli ping &>/dev/null; then
    echo "✓ Redis: 正常"
else
    echo "✗ Redis: 异常"
fi

# MinIO
if curl -s http://localhost:9000/minio/health/live &>/dev/null; then
    echo "✓ MinIO: 正常"
else
    echo "✗ MinIO: 异常"
fi

# 后端API
if curl -s http://localhost:8001/health &>/dev/null; then
    echo "✓ 后端API: 正常"
else
    echo "✗ 后端API: 异常"
fi

# 前端
if curl -s http://localhost:3000 &>/dev/null; then
    echo "✓ 前端: 正常"
else
    echo "✗ 前端: 异常"
fi

echo "=== 检查完成 ==="
```

### 定期维护任务

```bash
# 清理日志
find ~/EchoClip/logs -name "*.log" -mtime +7 -delete

# 清理临时文件
find /tmp -name "flowclip_*" -mtime +1 -delete

# 数据库维护
mysql -uyoutube_user -pyoutube_password -e "OPTIMIZE TABLE youtube_slicer.videos;"

# 更新系统包
sudo apt update && sudo apt upgrade -y
```

## 支持和帮助

如遇到问题，请：

1. 查看相关日志文件
2. 运行健康检查脚本
3. 检查系统资源使用情况
4. 查看项目文档和GitHub Issues

---

**注意**: 本部署指南适用于开发和测试环境。生产环境部署需要额外的安全配置和性能优化。