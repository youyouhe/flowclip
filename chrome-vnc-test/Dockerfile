FROM consol/ubuntu-xfce-vnc:latest

# 切换到root用户
USER root

# 更新软件包并安装编译工具
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    wget \
    git \
    vim \
    ffmpeg \
    build-essential \
    libssl-dev \
    libffi-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    openssh-server \
    openssh-client \
    supervisor \
    cron \
    rsync \
    unzip \
    zip \
    htop \
    tree \
    screen \
    tmux \
    netcat \
    telnet \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

# 编译安装Python 3.9
RUN cd /tmp && \
    wget https://www.python.org/ftp/python/3.9.16/Python-3.9.16.tgz && \
    tar xzf Python-3.9.16.tgz && \
    cd Python-3.9.16 && \
    ./configure --enable-optimizations --prefix=/usr/local && \
    make -j$(nproc) && \
    make altinstall && \
    ln -s /usr/local/bin/python3.9 /usr/bin/python3.9 && \
    ln -s /usr/local/bin/pip3.9 /usr/bin/pip3.9 && \
    cd / && rm -rf /tmp/Python-3.9.16

# 安装yt-dlp
RUN python3.9 -m pip install --upgrade pip && \
    python3.9 -m pip install yt-dlp

# 配置SSH服务
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' /etc/pam.d/sshd && \
    echo 'root:admin123' | chpasswd

# 创建SSH脚本目录
RUN mkdir -p /opt/scripts

# 创建常用目录
RUN mkdir -p /headless/Downloads /headless/Videos /headless/scripts

# 设置权限
RUN chown -R 1000:0 /headless

# 复制SSH启动脚本
COPY ssh-entrypoint.sh /usr/local/bin/ssh-entrypoint.sh
RUN chmod +x /usr/local/bin/ssh-entrypoint.sh

# 切换回普通用户
USER 1000

# 安装用户级别的Python包和远程执行工具
RUN python3.9 -m pip install --user \
    requests \
    beautifulsoup4 \
    selenium \
    paramiko \
    fabric \
    ansible \
    flask \
    fastapi \
    uvicorn