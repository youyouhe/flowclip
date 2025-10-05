# Chrome VNC 测试环境

## 快速启动

```bash
# 启动Chrome VNC容器
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止容器
docker-compose down
```

## 访问方式

### Web界面 (推荐)
访问: http://localhost:6901
密码: youtube123

### VNC客户端
- 地址: localhost:5901
- 密码: youtube123

## 使用说明

1. 启动容器后，等待约30秒让Chrome完全加载
2. 通过Web界面或VNC客户端连接
3. Chrome会自动启动，直接访问 YouTube
4. 登录你的Google账户

## 故障排除

如果Chrome启动较慢，可以查看日志：
```bash
docker logs youtube-chrome
```