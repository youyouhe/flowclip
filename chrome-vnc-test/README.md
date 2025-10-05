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

- **Python 3.9**: 完整的现代Python环境
- **yt-dlp**: YouTube视频下载工具
- **ffmpeg**: 视频处理工具
- **其他工具**: curl, wget, git, vim

## Python版本

容器内使用Python 3.9版本，支持现代Python特性和库。可以通过以下命令验证：

```bash
python3 --version
pip3 --version
```

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

## 远程执行和SSH访问

### SSH连接
- **端口**: 2222
- **用户**: root
- **密码**: admin123

```bash
# SSH连接到容器
ssh root@服务器IP -p 2222
# 密码: admin123
```

### 脚本执行
脚本文件放在 `./scripts/` 目录，会自动映射到容器的 `/headless/scripts`

```bash
# 通过SSH执行脚本
ssh root@服务器IP -p 2222 "python3.9 /headless/scripts/your_script.py"

# 通过文件传输上传脚本
scp -P 2222 your_script.py root@服务器IP:/headless/scripts/
```

### 已安装的远程执行工具

- **paramiko**: Python SSH客户端
- **fabric**: 远程命令执行工具
- **ansible**: 自动化配置管理
- **flask/fastapi**: Web API框架
- **screen/tmux**: 会话管理工具

## 故障排除

如果Chrome启动较慢，可以查看日志：
```bash
docker logs youtube-chrome
```