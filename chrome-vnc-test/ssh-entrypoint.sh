#!/bin/bash

# 启动SSH服务
service ssh start

# 查找并启动VNC startup脚本
if [ -f "/dockerstartup/startup.sh" ]; then
    /dockerstartup/startup.sh &
elif [ -f "/usr/local/bin/startup.sh" ]; then
    /usr/local/bin/startup.sh &
else
    # 直接启动VNC服务
    $STARTUPDIR/vnc_startup.sh &
fi

# 保持容器运行
tail -f /dev/null