# MinIO授权问题修复指南

## 问题描述
MinIO返回错误：
```xml
<Code>InvalidRequest</Code>
<Message>The authorization mechanism you have provided is not supported. Please use AWS4-HMAC-SHA256.</Message>
```

## 根本原因
1. MinIO服务器要求使用AWS Signature Version 4 (AWS4-HMAC-SHA256)
2. 客户端配置可能缺少必要的参数
3. URL替换逻辑可能破坏了签名完整性

## 已实施的修复

### 修复1：添加区域配置
在 `app/services/minio_client.py` 中添加了 `region="us-east-1"` 参数：

```python
self.client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
    region="us-east-1"  # 添加区域配置
)
```

### 修复2：改进URL生成逻辑
修复了 `get_file_url` 方法，使用 `urllib.parse` 安全地处理URL替换：

```python
# 安全地替换URL中的主机名，不破坏签名
from urllib.parse import urlparse, urlunparse

parsed = urlparse(url)
if settings.minio_endpoint != "localhost:9000" and "localhost" in parsed.netloc:
    # 构建新的netloc，保持端口
    if ":" in settings.minio_endpoint:
        new_netloc = settings.minio_endpoint
    else:
        port = parsed.port or 9000
        new_netloc = f"{settings.minio_endpoint}:{port}"
    
    # 重建URL，保持所有其他部分不变
    new_url = urlunparse((
        parsed.scheme,
        new_netloc,
        parsed.path,
        parsed.params,
        parsed.query,  # 保持签名参数完整
        parsed.fragment
    ))
    return new_url
```

### 修复3：添加连接测试功能
新增了 `test_connection` 方法用于诊断连接问题：

```python
async def test_connection(self) -> Dict[str, Any]:
    # 测试连接、桶存在性、策略配置等
```

## 验证步骤

### 1. 运行测试脚本
```bash
cd /home/cat/github/slice-youtube/backend
python test_minio_fix.py
```

### 2. 检查MinIO服务状态
```bash
# 如果使用Docker
docker-compose ps
docker-compose logs minio

# 检查MinIO健康状态
curl -f http://localhost:9000/minio/health/live
```

### 3. 环境变量验证
确保环境变量正确设置：

```bash
# 检查当前配置
echo $MINIO_ENDPOINT
echo $MINIO_ACCESS_KEY
echo $MINIO_SECRET_KEY
echo $MINIO_BUCKET_NAME
echo $MINIO_SECURE
```

预期值：
- MINIO_ENDPOINT=localhost:9000
- MINIO_ACCESS_KEY=minioadmin
- MINIO_SECRET_KEY=minioadmin
- MINIO_BUCKET_NAME=youtube-videos
- MINIO_SECURE=false

### 4. 手动测试MinIO
```bash
# 使用MinIO客户端测试
mc alias set myminio http://localhost:9000 minioadmin minioadmin
mc ls myminio/
```

## 常见问题解决

### 问题1：连接超时
**症状**: 无法连接到MinIO服务
**解决**: 
- 确保MinIO服务正在运行
- 检查防火墙设置
- 验证端口号是否正确

### 问题2：认证失败
**症状**: 返回401 Unauthorized
**解决**:
- 验证访问密钥和秘密密钥
- 检查是否区分大小写
- 重置MinIO凭据

### 问题3：签名错误
**症状**: AWS4-HMAC-SHA256相关错误
**解决**:
- 确保使用最新版本的minio-py库
- 检查系统时间是否正确（签名依赖时间同步）
- 验证区域配置

## 调试命令

### 检查MinIO版本
```bash
docker exec -it backend-minio-1 minio --version
```

### 查看MinIO日志
```bash
docker-compose logs minio -f
```

### 测试预签名URL
```python
import asyncio
from app.services.minio_client import minio_service

async def test_url():
    url = await minio_service.get_file_url("test.txt", 3600)
    print(f"Generated URL: {url}")

asyncio.run(test_url())
```

## 网络配置注意事项

### Docker环境
在Docker环境中，确保：
- 容器间网络通信正常
- 主机名解析正确
- 端口映射正确

### 生产环境
在生产环境中：
- 使用HTTPS (MINIO_SECURE=true)
- 配置正确的域名
- 设置适当的CORS策略

## 验证修复成功

运行以下命令验证修复：

```bash
# 1. 重启服务
docker-compose restart

# 2. 运行测试
python test_minio_fix.py

# 3. 检查API端点
curl -X GET "http://localhost:8001/api/v1/videos/1/download-url" -H "Authorization: Bearer YOUR_TOKEN"
```

如果所有测试通过，MinIO授权问题应该已经解决。