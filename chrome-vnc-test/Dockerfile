FROM consol/ubuntu-xfce-vnc:focal-latest

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

# 安装Python 3.9和开发工具
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
    python3.9 \
    python3.9-pip \
    python3.9-dev \
    python3.9-venv && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1 && \
    update-alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.9 1

# 安装yt-dlp
RUN python3.9 -m pip install --upgrade pip && \
    pip3 install yt-dlp

# 创建常用目录
RUN mkdir -p /headless/Downloads /headless/Videos

# 设置权限
RUN chown -R 1000:0 /headless

# 切换回普通用户
USER 1000

# 安装用户级别的Python包
RUN python3.9 -m pip install --user requests beautifulsoup4 selenium