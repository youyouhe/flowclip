# 独立TUS回调服务器部署指南

## 概述

独立TUS回调服务器解决了原有多进程Celery Worker环境下的回调丢失问题。通过将回调服务器运行在独立容器中，确保了TUS ASR结果的可靠接收。

## 架构优势

1. **消除进程间竞争**：不再依赖Celery Worker进程内的回调服务器
2. **提高可靠性**：独立容器确保回调服务持续可用
3. **简化管理**：统一的Redis状态管理，易于监控和调试
4. **资源隔离**：回调服务器与Worker进程完全隔离

## 部署步骤

### 1. 更新Docker Compose配置

独立回调服务器已添加到`docker-compose.yml`：

```yaml
callback-server:
  build:
    context: ./backend
    dockerfile: Dockerfile
  container_name: flowclip-callback
  command: python callback_server.py
  ports:
    - "9090:9090"
  environment:
    - REDIS_URL=redis://redis:6379
    - CALLBACK_HOST=0.0.0.0
    - CALLBACK_PORT=9090
```

### 2. 配置系统参数

在系统配置中设置以下参数：

```sql
INSERT INTO system_configs (config_key, config_value, config_name, config_type) VALUES
('tus_use_standalone_callback', 'true', '使用独立回调服务器', 'boolean');
```

### 3. 重启服务

```bash
# 停止现有服务
docker-compose down

# 重新启动所有服务
docker-compose up -d

# 检查回调服务器状态
docker-compose logs callback-server
```

## 监控和调试

### 健康检查

```bash
# 检查回调服务器健康状态
curl http://localhost:9090/health

# 查看统计信息
curl http://localhost:9090/stats
```

### 日志查看

```bash
# 查看回调服务器日志
docker-compose logs -f callback-server

# 查看Celery Worker日志
docker-compose logs -f celery-worker
```

### Redis监控

```bash
# 连接到Redis容器
docker-compose exec redis redis-cli

# 查看回调任务统计
HGETALL tus_callback_stats

# 查看待处理任务
KEYS tus_callback:*

# 查看缓存结果
KEYS tus_result:*
```

## 故障排除

### 常见问题

1. **回调服务器无法启动**
   - 检查端口9090是否被占用
   - 验证Redis连接是否正常
   - 查看容器日志排查错误

2. **任务回调丢失**
   - 检查TUS API服务能否访问回调服务器
   - 验证防火墙设置
   - 确认网络连接

3. **任务超时**
   - 调整TUS超时设置
   - 检查ASR服务状态
   - 监控Redis内存使用

### 回滚方案

如需回滚到原有方案：

1. 修改配置禁用独立回调服务器：
```sql
UPDATE system_configs SET config_value = 'false' WHERE config_key = 'tus_use_standalone_callback';
```

2. 重启Celery Worker服务：
```bash
docker-compose restart celery-worker
```

## 性能优化

### 调优参数

- **Redis内存**：根据并发任务数调整Redis内存限制
- **回调服务器资源**：根据负载调整CPU和内存限制
- **超时设置**：根据ASR服务响应时间调整超时参数

### 扩展方案

- **负载均衡**：多个回调服务器实例通过负载均衡器分发
- **集群模式**：使用Redis Cluster支持大规模部署
- **监控告警**：集成Prometheus和Grafana进行监控

## 安全考虑

1. **网络安全**：回调服务器仅接受内部网络访问
2. **认证机制**：可添加API密钥验证
3. **日志审计**：记录所有回调请求和响应
4. **限流保护**：防止恶意请求过载

## 维护计划

1. **定期清理**：自动清理过期的任务和结果
2. **备份恢复**：定期备份Redis数据
3. **性能监控**：持续监控关键指标
4. **版本更新**：定期更新容器镜像