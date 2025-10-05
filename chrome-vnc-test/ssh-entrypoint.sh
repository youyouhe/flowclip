#!/bin/bash

# 启动SSH服务
service ssh start

# 启动VNC和noVNC服务
/usr/bin/startup.sh &

# 保持容器运行
tail -f /dev/null