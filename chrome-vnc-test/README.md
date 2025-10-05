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

**注意**: 如果密码无效，尝试默认密码 `vncpassword`

## 使用说明

1. 启动容器后，等待约30秒让桌面环境完全加载
2. 通过Web界面或VNC客户端连接
3. 在桌面中找到Chrome浏览器并启动
4. 在Chrome中访问 YouTube
5. 登录你的Google账户

**注意**: 这个镜像提供完整的Ubuntu桌面环境，Chrome需要手动启动

## 已安装工具

- **Python 3**: 完整的Python环境
- **yt-dlp**: YouTube视频下载工具
- **ffmpeg**: 视频处理工具
- **其他工具**: curl, wget, git, vim

## 使用yt-dlp

```bash
# 下载视频
yt-dlp "https://www.youtube.com/watch?v=VIDEO_ID"

# 下载音频
yt-dlp -x --audio-format mp3 "URL"

# 查看可用格式
yt-dlp -F "URL"
```

下载的文件会保存在 `/headless/Downloads` 目录，并映射到宿主机的 `./downloads` 文件夹。

## 故障排除

如果Chrome启动较慢，可以查看日志：
```bash
docker logs youtube-chrome
```