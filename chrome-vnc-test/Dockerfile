FROM consol/ubuntu-xfce-vnc:latest

# 切换到root用户
USER root

# 更新软件包并安装Python和工具
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    wget \
    git \
    vim \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 安装yt-dlp（使用wget方式，避免pip版本问题）
RUN wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O /usr/local/bin/yt-dlp && \
    chmod a+rx /usr/local/bin/yt-dlp

# 创建常用目录
RUN mkdir -p /headless/Downloads /headless/Videos

# 设置权限
RUN chown -R 1000:0 /headless

# 切换回普通用户
USER 1000

# 安装用户级别的Python包
RUN python3 -m pip install --user --upgrade "pip<21.0" && \
    python3 -m pip install --user requests beautifulsoup4 selenium