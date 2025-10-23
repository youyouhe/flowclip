# EchoClip PM2 Bootstrap配置部署指南

**更新日期**: 2025年1月24日
**版本**: v1.0
**适用场景**: 从Docker Compose迁移到PM2部署，解决MySQL密码循环依赖问题

## 目录

1. [问题背景](#问题背景)
2. [解决方案概述](#解决方案概述)
3. [系统架构](#系统架构)
4. [部署前准备](#部署前准备)
5. [详细部署步骤](#详细部署步骤)
6. [配置系统详解](#配置系统详解)
7. [故障排除](#故障排除)
8. [测试验证](#测试验证)
9. [维护指南](#维护指南)

---

## 问题背景

### 循环依赖问题

在PM2部署环境中遇到了以下循环依赖：

1. **Backend应用需要连接MySQL数据库**
2. **MySQL密码存储在数据库的系统配置表中**
3. **没有密码无法连接数据库来读取密码**
4. **没有数据库连接无法写入初始密码**

### 原有系统的局限性

- Docker Compose环境使用服务名和共享网络解决连接问题
- PM2直接部署时应用在数据库连接前无法获取配置
- 环境变量管理复杂，容易出错

---

## 解决方案概述

### Bootstrap配置策略

实现了**分层配置系统**，包含三个层次：

```
┌─────────────────┐
│   Bootstrap配置   │ ← 初始启动使用，打破循环依赖
├─────────────────┤
│   数据库配置     │ ← Bootstrap写入后成为主要配置源
├─────────────────┤
│   环境变量       │ ← 作为备用和覆盖配置源
└─────────────────┘
```

### 核心特性

- ✅ **自动密码读取**: 从`~/credentials.txt`读取动态生成的密码
- ✅ **一次性初始化**: 配置写入数据库后bootstrap自动停用
- ✅ **向后兼容**: 不影响现有配置管理方式
- ✅ **容错机制**: 多种配置读取方式，确保系统稳定
- ✅ **安全性**: 使用文件权限保护敏感信息

---

## 系统架构

### 文件结构

```
EchoClip/
├── backend/
│   ├── bootstrap_config.py          # ← 新增：Bootstrap配置管理器
│   ├── app/
│   │   └── core/
│   │       └── config.py            # ← 修改：支持Bootstrap配置加载
│   └── app/
│       └── main.py                  # ← 修改：启动时初始化数据库配置
├── deploy_pm2.sh                    # ← 修改：集成Bootstrap初始化
├── install_root.sh                  # ← 现有：生成动态密码
└── ecosystem.config.js              # ← 现有：PM2服务配置
```

### 工作流程

```
1. install_root.sh (root用户)
   ├── 生成随机密码
   ├── 保存到 /root/flowclip_credentials.txt
   └── 复制到 /home/flowclip/credentials.txt

2. deploy_pm2.sh (flowclip用户)
   ├── 读取 credentials.txt
   ├── 设置环境变量
   ├── 初始化 bootstrap配置
   └── 启动PM2服务

3. 应用启动流程
   ├── 加载bootstrap配置
   ├── 连接数据库
   ├── 将配置写入数据库
   ├── 标记bootstrap为已初始化
   └── 后续启动从数据库读取配置
```

---

## 部署前准备

### 系统要求

- **操作系统**: Ubuntu 20.04+ / CentOS 7+
- **用户权限**: root用户安装，flowclip用户部署
- **Python**: 3.11+
- **Node.js**: 18+
- **系统服务**: MySQL 8.0, Redis, MinIO

### 必需文件检查

```bash
# 检查install_root.sh是否执行完成
sudo ls -la /root/flowclip_credentials.txt

# 检查凭证文件是否复制到flowclip用户
ls -la /home/flowclip/credentials.txt

# 检查文件权限
sudo ls -la /root/flowclip_credentials.txt
ls -la /home/flowclip/credentials.txt
```

### 预期文件内容

`/home/flowclip/credentials.txt` 应包含：

```
========================================
    Flowclip 系统凭据信息
========================================
生成时间: 2025-01-24 xx:xx:xx
服务器IP: xxx.xxx.xxx.xxx

数据库凭据:
MYSQL_ROOT_PASSWORD=xxxxxxxxxxxxxxxxxx
MYSQL_APP_PASSWORD=xxxxxxxxxxxxxxxxxx
MYSQL_DATABASE=youtube_slicer
MYSQL_USER=youtube_user

MinIO凭据:
MINIO_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MINIO_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MINIO_BUCKET=youtube-videos

应用凭据:
SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 详细部署步骤

### 第1步：切换到flowclip用户

```bash
# 切换用户
sudo su - flowclip

# 进入项目目录
cd EchoClip
```

### 第2步：检查代码更新

```bash
# 确保代码是最新的
git status
git pull origin main

# 验证新文件是否存在
ls -la backend/bootstrap_config.py
```

### 第3步：验证系统服务状态

```bash
# 检查MySQL
systemctl status mysql

# 检查Redis
systemctl status redis-server

# 检查MinIO
systemctl status minio

# 检查端口监听
netstat -tuln | grep -E '3306|6379|9000|9001'
```

### 第4步：执行PM2部署

```bash
# 执行部署脚本
./deploy_pm2.sh
```

**部署过程中的关键步骤**：

1. **停止现有服务**
   ```bash
   pm2 stop all || true
   pm2 delete all || true
   ```

2. **代码备份和更新**
   ```bash
   git pull origin main
   ```

3. **Bootstrap配置初始化**
   ```bash
   # 读取凭证文件
   MYSQL_ROOT_PASSWORD=$(grep "MYSQL_ROOT_PASSWORD=" "$HOME/credentials.txt" | cut -d'=' -f2)
   MYSQL_APP_PASSWORD=$(grep "MYSQL_APP_PASSWORD=" "$HOME/credentials.txt" | cut -d'=' -f2)

   # 设置环境变量
   export DYNAMIC_MYSQL_ROOT_PASSWORD="$MYSQL_ROOT_PASSWORD"
   export DYNAMIC_MYSQL_PASSWORD="$MYSQL_APP_PASSWORD"

   # 初始化bootstrap配置
   python -c "
   from bootstrap_config import get_bootstrap_config, init_bootstrap_from_deployment
   init_bootstrap_from_deployment()
   config = get_bootstrap_config()
   config.update_from_env()
   "
   ```

4. **数据库迁移**
   ```bash
   alembic upgrade head
   ```

5. **启动PM2服务**
   ```bash
   pm2 start ecosystem.config.js --env production
   ```

### 第5步：验证部署结果

```bash
# 检查PM2服务状态
pm2 status

# 检查服务日志
pm2 logs flowclip-backend --lines 20

# 验证健康检查
curl -f http://localhost:8001/health
curl -f http://localhost:3000
curl -f http://localhost:9090/health
```

---

## 配置系统详解

### Bootstrap配置管理器

**文件**: `backend/bootstrap_config.py`

#### 核心功能

1. **凭证文件自动读取**
   ```python
   def get_env_config(self) -> Dict[str, Any]:
       # 从 ~/credentials.txt 读取动态密码
       credentials_file = os.path.expanduser("~/credentials.txt")
       if os.path.exists(credentials_file):
           with open(credentials_file, 'r', encoding='utf-8') as f:
               for line in f:
                   if line.startswith('MYSQL_ROOT_PASSWORD='):
                       config["mysql"]["root_password"] = line.split('=', 1)[1]
                   # ... 其他配置项
   ```

2. **配置持久化**
   ```python
   def save_config(self):
       with open(self.config_file, 'w', encoding='utf-8') as f:
           json.dump(self.config, f, indent=2, ensure_ascii=False)
   ```

3. **初始化状态管理**
   ```python
   def is_initialized(self) -> bool:
       return self.get('initialized', False)

   def mark_initialized(self):
       self.set('initialized', True)
   ```

#### 配置文件位置

- **Bootstrap配置**: `backend/.bootstrap_config.json`
- **凭证文件**: `~/credentials.txt`

### 应用配置加载

**文件**: `backend/app/core/config.py`

#### 修改内容

```python
# 添加bootstrap配置支持
try:
    from bootstrap_config import get_bootstrap_config
    bootstrap_config = get_bootstrap_config()
    USE_BOOTSTRAP = True
except ImportError:
    bootstrap_config = None
    USE_BOOTSTRAP = False

class Settings(BaseSettings):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if USE_BOOTSTRAP and bootstrap_config:
            self.load_from_bootstrap()

    def load_from_bootstrap(self):
        if not bootstrap_config.is_initialized():
            # 从bootstrap加载MySQL密码等关键配置
            mysql_config = bootstrap_config.get('mysql', {})
            if mysql_config.get('password'):
                self.mysql_password = mysql_config['password']
                self.database_url = bootstrap_config.get_database_url()
```

### 应用启动集成

**文件**: `backend/app/main.py`

#### 启动流程修改

```python
@app.on_event("startup")
async def startup_event():
    # ... 其他初始化代码

    # Bootstrap配置初始化
    if USE_BOOTSTRAP and bootstrap_config and not bootstrap_config.is_initialized():
        logging.info("Initializing system configuration from bootstrap...")

        # 将bootstrap配置写入数据库
        mysql_config = bootstrap_config.get('mysql', {})
        for key, value in mysql_config.items():
            db_key = f"mysql_{key}" if key != 'password' else 'mysql_password'
            SystemConfigService.set_config_sync(db, db_key, str(value), "数据库配置", "数据库配置")

        # 标记为已初始化
        bootstrap_config.mark_initialized()
        logging.info("Bootstrap configuration initialized and saved to database")

    # 从数据库加载系统配置
    SystemConfigService.update_settings_from_db_sync(db)
```

---

## 故障排除

### 常见问题及解决方案

#### 1. 凭证文件不存在

**症状**:
```
Credentials file not found: /home/flowclip/credentials.txt, using environment variables
```

**解决方案**:
```bash
# 检查文件是否存在
ls -la ~/credentials.txt

# 如果不存在，从root用户复制
sudo cp /root/flowclip_credentials.txt ~/credentials.txt
sudo chown flowclip:flowclip ~/credentials.txt
sudo chmod 600 ~/credentials.txt
```

#### 2. Bootstrap配置初始化失败

**症状**:
```
Bootstrap 配置初始化失败，继续部署...
```

**解决方案**:
```bash
# 手动测试bootstrap配置
cd backend
python bootstrap_config.py

# 检查配置内容
python -c "
from bootstrap_config import get_bootstrap_config
config = get_bootstrap_config()
print('MySQL password length:', len(config.get('mysql.password', '')))
print('Config file:', config.config_file)
"
```

#### 3. 数据库连接失败

**症状**:
```
Failed to connect to database. Exiting.
```

**解决方案**:
```bash
# 手动测试数据库连接
mysql -uyoutube_user -p$(grep 'MYSQL_APP_PASSWORD=' ~/credentials.txt | cut -d'=' -f2) youtube_slicer -e "SELECT 1;"

# 检查bootstrap配置
python -c "
from bootstrap_config import get_bootstrap_config
config = get_bootstrap_config()
print('Database URL:', config.get_database_url())
"
```

#### 4. PM2服务启动失败

**症状**:
```
PM2 服务启动失败！
```

**解决方案**:
```bash
# 检查详细日志
pm2 logs flowclip-backend --err --lines 50

# 手动启动测试
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 调试命令集

```bash
# 1. 检查系统服务状态
systemctl status mysql redis-server minio

# 2. 检查端口监听
netstat -tuln | grep -E '3306|6379|9000|9001|8001|3000|9090'

# 3. 检查PM2状态
pm2 status
pm2 monit

# 4. 测试bootstrap配置
cd backend && python bootstrap_config.py

# 5. 测试数据库连接
mysql -uyoutube_user -p$(grep 'MYSQL_APP_PASSWORD=' ~/credentials.txt | cut -d'=' -f2) youtube_slicer

# 6. 检查应用健康状态
curl -f http://localhost:8001/health
curl -f http://localhost:3000
curl -f http://localhost:9090/health
```

---

## 测试验证

### 完整测试流程

#### 1. Bootstrap配置测试

```bash
# 测试bootstrap配置生成
cd backend
python bootstrap_config.py

# 预期输出:
# Loading configuration from bootstrap...
# Updated database URL from bootstrap config
# Bootstrap configuration loaded successfully
# Bootstrap config:
# {
#   "mysql": {
#     "password": "xxxxxxxx",
#     "user": "youtube_user",
#     "host": "127.0.0.1",
#     "port": 3306,
#     "database": "youtube_slicer"
#   },
#   "initialized": false
# }
# Database URL: mysql+aiomysql://youtube_user:xxxxxxxx@127.0.0.1:3306/youtube_slicer?charset=utf8mb4
# Initialized: false
```

#### 2. 数据库连接测试

```bash
# 使用bootstrap配置连接数据库
python -c "
from bootstrap_config import get_bootstrap_config
config = get_bootstrap_config()
import mysql.connector
try:
    conn = mysql.connector.connect(
        host=config.get('mysql.host'),
        port=config.get('mysql.port'),
        user=config.get('mysql.user'),
        password=config.get('mysql.password'),
        database=config.get('mysql.database')
    )
    print('✓ 数据库连接成功')
    conn.close()
except Exception as e:
    print(f'✗ 数据库连接失败: {e}')
"
```

#### 3. 应用启动测试

```bash
# 手动启动Backend应用
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# 在另一个终端检查
curl -f http://localhost:8001/health

# 预期输出:
# {"status": "healthy"}
```

#### 4. PM2完整部署测试

```bash
# 执行完整部署
./deploy_pm2.sh

# 检查所有服务状态
pm2 status

# 验证所有服务
services=(
    "Backend API:http://localhost:8001/health"
    "Frontend:http://localhost:3000"
    "TUS Callback Server:http://localhost:9090/health"
)

for service_info in "${services[@]}"; do
    name=$(echo $service_info | cut -d: -f1)
    url=$(echo $service_info | cut -d: -f2-)

    if curl -f -s "$url" > /dev/null 2>&1; then
        echo "✓ $name - OK"
    else
        echo "✗ $name - FAILED"
    fi
done
```

### 配置验证测试

#### 验证数据库配置是否正确写入

```bash
# 检查数据库中的配置
mysql -uyoutube_user -p$(grep 'MYSQL_APP_PASSWORD=' ~/credentials.txt | cut -d'=' -f2) youtube_slicer -e "
SELECT key, value, category FROM system_configs WHERE key LIKE 'mysql_%';
"

# 预期看到MySQL相关配置已写入数据库
```

#### 验证Bootstrap状态

```bash
# 检查bootstrap是否已标记为已初始化
python -c "
from bootstrap_config import get_bootstrap_config
config = get_bootstrap_config()
print('Bootstrap initialized:', config.is_initialized())
"
```

---

## 维护指南

### 日常运维

#### 1. 服务状态检查

```bash
# 每日检查脚本
#!/bin/bash
echo "=== EchoClip 服务状态检查 ==="
date

# 检查系统服务
echo "1. 系统服务状态:"
systemctl is-active mysql redis-server minio

# 检查PM2服务
echo "2. PM2服务状态:"
pm2 status | grep -E "(online|stopped|errored)"

# 检查端口监听
echo "3. 端口监听状态:"
netstat -tuln | grep -E '3306|6379|9000|9001|8001|3000|9090'

# 检查应用健康
echo "4. 应用健康状态:"
curl -s http://localhost:8001/health > /dev/null && echo "Backend: OK" || echo "Backend: FAILED"
curl -s http://localhost:3000 > /dev/null && echo "Frontend: OK" || echo "Frontend: FAILED"
curl -s http://localhost:9090/health > /dev/null && echo "TUS Callback: OK" || echo "TUS Callback: FAILED"

echo "=== 检查完成 ==="
```

#### 2. 日志监控

```bash
# 查看PM2日志
pm2 logs --lines 100

# 查看特定服务日志
pm2 logs flowclip-backend --lines 50
pm2 logs flowclip-frontend --lines 50
pm2 logs flowclip-callback --lines 50

# 查看系统日志
journalctl -u mysql -f
journalctl -u redis-server -f
journalctl -u minio -f
```

#### 3. 性能监控

```bash
# PM2监控
pm2 monit

# 系统资源监控
htop
iostat -x 1
```

### 配置更新

#### 1. 修改数据库密码

```bash
# 1. 停止应用
pm2 stop flowclip-backend

# 2. 更新MySQL密码
sudo mysql -uroot -p -e "
ALTER USER 'youtube_user'@'%' IDENTIFIED BY 'new_password';
ALTER USER 'youtube_user'@'localhost' IDENTIFIED BY 'new_password';
FLUSH PRIVILEGES;
"

# 3. 更新凭证文件
sudo vim /home/flowclip/credentials.txt
# 修改 MYSQL_APP_PASSWORD=new_password

# 4. 删除bootstrap配置文件
rm -f backend/.bootstrap_config.json

# 5. 重启应用
pm2 start flowclip-backend
```

#### 2. 修改其他配置

```bash
# 通过API修改配置
curl -X PUT http://localhost:8001/api/v1/system-config \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "minio_endpoint",
    "value": "new-endpoint:9000",
    "description": "MinIO服务端点",
    "category": "MinIO配置"
  }'

# 或直接修改数据库
mysql -uyoutube_user -p youtube_slicer -e "
UPDATE system_configs
SET value = 'new-endpoint:9000'
WHERE key = 'minio_endpoint';
"
```

### 备份和恢复

#### 1. 配置文件备份

```bash
# 备份关键配置文件
BACKUP_DIR="/home/flowclip/backups/config_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 备份凭证文件
cp ~/credentials.txt "$BACKUP_DIR/"

# 备份bootstrap配置
cp backend/.bootstrap_config.json "$BACKUP_DIR/" 2>/dev/null || true

# 备份PM2配置
cp ecosystem.config.js "$BACKUP_DIR/"

# 备份数据库配置
mysqldump -uyoutube_user -p$(grep 'MYSQL_APP_PASSWORD=' ~/credentials.txt | cut -d'=' -f2) youtube_slicer system_configs > "$BACKUP_DIR/system_configs.sql"

echo "配置备份完成: $BACKUP_DIR"
```

#### 2. 系统重置

```bash
# 如果需要完全重置bootstrap配置
rm -f backend/.bootstrap_config.json

# 清除数据库中的系统配置（谨慎操作）
mysql -uyoutube_user -p youtube_slicer -e "DELETE FROM system_configs;"

# 重新部署
./deploy_pm2.sh
```

### 安全维护

#### 1. 凭证文件安全

```bash
# 检查凭证文件权限
ls -la ~/credentials.txt

# 应该显示：
# -rw------- 1 flowclip flowclip xxx Jan 24 xx:xx credentials.txt

# 如果权限不对，修复权限
chmod 600 ~/credentials.txt
chown flowclip:flowclip ~/credentials.txt
```

#### 2. 定期密码轮换

```bash
# 生成新密码
NEW_MYSQL_PASSWORD=$(openssl rand -base64 20 | tr -d "=+/" | cut -c1-16)
NEW_MINIO_SECRET=$(openssl rand -base64 40 | tr -d "=+/" | cut -c1-32)

# 更新系统和配置
# ... 按照配置更新流程操作
```

---

## 总结

本Bootstrap配置部署指南解决了EchoClip应用从Docker Compose迁移到PM2部署时的核心问题：

### 解决的核心问题

1. **循环依赖**: 通过Bootstrap配置打破MySQL密码依赖循环
2. **配置管理**: 实现分层配置系统，支持多种配置源
3. **自动化部署**: 集成到现有部署流程，无需人工干预
4. **向后兼容**: 保持与现有配置系统的兼容性

### 技术优势

- ✅ **零停机部署**: 支持热更新和滚动重启
- ✅ **容错机制**: 多重备用方案确保系统稳定性
- ✅ **安全性**: 基于文件权限的敏感信息保护
- ✅ **可维护性**: 清晰的配置层次和生命周期管理

### 适用场景

- 从Docker环境迁移到PM2部署
- 解决数据库连接配置的循环依赖问题
- 需要自动化配置管理的生产环境
- 多环境配置统一管理的场景

通过本指南的实施，EchoClip应用可以在PM2环境中稳定运行，同时保持配置的灵活性和安全性。

---

**文档维护**: 本指南应随系统更新同步维护，确保信息的准确性和时效性。