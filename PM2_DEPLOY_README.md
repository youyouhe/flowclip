# EchoClip PM2 部署指南

本指南详细说明了如何使用 PM2 部署 EchoClip 应用，替代原来的 Docker Compose 方式。

## 📋 部署架构

基于 `docker-compose.yml` 分析，我们将以下服务迁移到 PM2：

### 核心服务
1. **Backend API** (端口 8001) - FastAPI 后端服务
2. **Frontend** (端口 3000) - React 前端 (生产模式)
3. **TUS Callback Server** (端口 9090) - TUS 回调服务
4. **Celery Worker** - 后台任务处理
5. **Celery Beat** - 定时任务调度
6. **MCP Server** (端口 8002) - MCP 服务

### 系统依赖 (仍需系统级服务)
- **MySQL** (端口 3307) - 数据库
- **Redis** (端口 6379) - 缓存和消息队列
- **MinIO** (端口 9000/9001) - 对象存储

## 🚀 快速部署

### 1. 首次部署

```bash
# 登录服务器
ssh flowclip@107.173.223.214

# 进入项目目录
cd EchoClip

# 执行完整部署
./deploy_pm2.sh
```

### 2. 日常更新

```bash
# 快速更新和重启
./quick_start.sh
```

### 3. 服务状态检查

```bash
# 检查所有服务状态
./check_services.sh
```

## 📁 脚本说明

### deploy_pm2.sh - 完整部署脚本
- ✅ 停止现有服务
- ✅ 备份当前代码
- ✅ 拉取最新代码
- ✅ 安装/更新依赖
- ✅ 构建前端生产版本
- ✅ 检查系统服务状态
- ✅ 运行数据库迁移
- ✅ 启动所有 PM2 服务
- ✅ 健康检查

### quick_start.sh - 快速启动脚本
- ✅ 快速更新代码
- ✅ 更新依赖
- ✅ 重启服务
- ⏭️ 跳过系统检查和备份

### check_services.sh - 服务检查脚本
- ✅ PM2 服务状态
- ✅ 系统服务状态
- ✅ 端口占用检查
- ✅ 健康检查
- ✅ 资源使用情况
- ✅ 错误日志查看

## 🔧 配置文件

### ecosystem.config.js - PM2 配置
包含所有服务的配置：
- 启动命令和参数
- 环境变量
- 内存限制
- 日志配置
- 重启策略

### 关键配置变更

#### 前端生产模式
```javascript
{
  name: 'flowclip-frontend',
  script: '/usr/bin/npm',
  args: 'run preview',  // 改为生产模式
  env: {
    NODE_ENV: 'production',
    VITE_API_URL: '/api'
  }
}
```

#### Celery 启动方式
```javascript
{
  name: 'flowclip-celery-worker',
  script: '/home/flowclip/EchoClip/venv/bin/python',
  args: 'start_celery.py worker --loglevel=info --concurrency=4'
}
```

## 🌐 服务访问地址

| 服务 | 端口 | 访问地址 |
|------|------|----------|
| 前端 | 3000 | http://107.173.223.214:3000 |
| 后端API | 8001 | http://107.173.223.214:8001 |
| MinIO 控制台 | 9001 | http://107.173.223.214:9001 |
| TUS 回调 | 9090 | http://107.173.223.214:9090 |
| MCP 服务 | 8002 | http://107.173.223.214:8002 |

## 📊 常用管理命令

### PM2 基础命令
```bash
# 查看所有服务状态
pm2 status

# 查看日志
pm2 logs                    # 所有服务日志
pm2 logs flowclip-backend   # 特定服务日志

# 重启服务
pm2 restart all             # 重启所有服务
pm2 restart flowclip-backend # 重启特定服务

# 停止服务
pm2 stop all                # 停止所有服务
pm2 stop flowclip-backend   # 停止特定服务

# 删除服务
pm2 delete all              # 删除所有服务
pm2 delete flowclip-backend # 删除特定服务

# 监控面板
pm2 monit
```

### 系统服务管理
```bash
# MySQL
sudo systemctl status mysql
sudo systemctl restart mysql

# Redis
sudo systemctl status redis
sudo systemctl restart redis

# MinIO (手动启动)
pkill -f "minio server"
nohup minio server /home/flowclip/minio-data --console-address ":9001" &
```

## 🔍 故障排除

### 1. 服务启动失败
```bash
# 查看详细错误日志
pm2 logs --err

# 检查配置文件
cat ecosystem.config.js

# 手动测试启动
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 2. 数据库连接问题
```bash
# 检查 MySQL 服务状态
sudo systemctl status mysql

# 测试数据库连接
mysql -h localhost -P 3307 -u youtube_user -p youtube_password

# 检查数据库配置
grep -E "(DATABASE_URL|MYSQL_)" .env
```

### 3. 前端构建失败
```bash
# 清理并重新安装
cd frontend
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
npm run build
```

### 4. 端口占用问题
```bash
# 查看端口占用
sudo netstat -tuln | grep :8001

# 结束占用进程
sudo lsof -ti:8001 | xargs kill -9
```

## 📁 重要文件位置

| 文件/目录 | 位置 | 说明 |
|-----------|------|------|
| PM2 配置 | `/home/flowclip/EchoClip/ecosystem.config.js` | PM2 服务配置 |
| PM2 日志 | `~/.pm2/logs/` | 所有服务日志 |
| 备份文件 | `/home/flowclip/backups/` | 代码备份 |
| MinIO 数据 | `/home/flowclip/minio-data/` | 对象存储数据 |
| 虚拟环境 | `/home/flowclip/EchoClip/backend/venv/` | Python 环境 |
| 前端构建 | `/home/flowclip/EchoClip/frontend/dist/` | 生产构建文件 |

## 🔄 部署流程

### 本地开发流程
1. 本地代码修改和测试
2. Git 提交和推送
   ```bash
   git add .
   git commit -m "feat: 添加新功能"
   git push origin main
   ```

### 服务器部署流程
1. 登录服务器拉取最新代码
   ```bash
   ssh flowclip@107.173.223.214
   cd EchoClip
   git pull origin main
   ```

2. 执行部署脚本
   ```bash
   # 首次部署或重大更新
   ./deploy_pm2.sh

   # 日常更新
   ./quick_start.sh
   ```

3. 检查部署状态
   ```bash
   ./check_services.sh
   ```

## 🎯 性能优化

### 内存限制配置
- Backend API: 1GB
- Celery Worker: 2GB
- Frontend: 512MB
- 其他服务: 256MB

### 并发配置
- Celery Worker: 4 并发
- 可根据服务器配置调整 `ecosystem.config.js`

## 📞 监控和告警

建议设置以下监控：
- 服务存活检查
- 内存使用率监控
- 磁盘空间监控
- 错误日志监控

可以使用 `pm2 monit` 进行实时监控。